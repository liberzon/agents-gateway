import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from supervisor.models import ExecutionResult
from remote_agent.runtime.base import ContainerRuntime

logger = logging.getLogger(__name__)


class KubernetesRuntime(ContainerRuntime):
    """Kubernetes container runtime for cluster-based scaling.

    Coding worker pods are substantial — recommend dedicated node pools
    with 4+ vCPU / 8GB+ per coding pod.
    """

    def __init__(
        self,
        namespace: str = "supervisor-workers",
        node_selector: Optional[Dict[str, str]] = None,
    ) -> None:
        self._namespace = namespace
        self._node_selector = node_selector or {}
        self._api: Any = None
        self._batch_api: Any = None

    def _init_client(self) -> None:
        if self._api is not None:
            return
        try:
            from kubernetes import client, config  # type: ignore[import-not-found]

            config.load_incluster_config()
        except Exception:
            try:
                from kubernetes import config  # type: ignore[import-not-found]

                config.load_kube_config()
            except Exception:
                raise RuntimeError("Cannot connect to Kubernetes cluster")
        from kubernetes import client  # type: ignore[import-not-found]

        self._api = client.CoreV1Api()
        self._batch_api = client.BatchV1Api()

    async def create_container(
        self,
        image: str,
        workspace_dir: str,
        command: list[str],
        env: Optional[Dict[str, str]] = None,
        cpu_limit: Optional[float] = None,
        memory_limit_mb: Optional[int] = None,
        network_enabled: bool = False,
        labels: Optional[Dict[str, str]] = None,
    ) -> str:
        self._init_client()
        from kubernetes import client as k8s

        import uuid

        job_name = f"worker-{uuid.uuid4().hex[:8]}"

        # Build resource requirements
        resources: Dict[str, Any] = {}
        if cpu_limit or memory_limit_mb:
            limits: Dict[str, str] = {}
            requests: Dict[str, str] = {}
            if cpu_limit:
                limits["cpu"] = str(cpu_limit)
                requests["cpu"] = str(cpu_limit / 2)
            if memory_limit_mb:
                limits["memory"] = f"{memory_limit_mb}Mi"
                requests["memory"] = f"{memory_limit_mb // 2}Mi"
            resources = {"limits": limits, "requests": requests}

        # Build env vars
        env_vars = [k8s.V1EnvVar(name=k, value=v) for k, v in (env or {}).items()]

        container = k8s.V1Container(
            name="worker",
            image=image,
            command=command,
            env=env_vars,
            resources=k8s.V1ResourceRequirements(**resources) if resources else None,
            volume_mounts=[k8s.V1VolumeMount(name="workspace", mount_path="/workspace")],
        )

        pod_spec = k8s.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            node_selector=self._node_selector or None,
            volumes=[k8s.V1Volume(name="workspace", empty_dir=k8s.V1EmptyDirVolumeSource())],
        )

        job = k8s.V1Job(
            metadata=k8s.V1ObjectMeta(name=job_name, namespace=self._namespace, labels=labels or {}),
            spec=k8s.V1JobSpec(
                template=k8s.V1PodTemplateSpec(spec=pod_spec),
                backoff_limit=0,
                ttl_seconds_after_finished=300,
            ),
        )

        await asyncio.to_thread(self._batch_api.create_namespaced_job, self._namespace, job)
        logger.info(f"Created K8s job: {job_name}")
        return job_name

    async def stream_output(self, container_id: str) -> AsyncGenerator[str, None]:  # type: ignore[override]
        self._init_client()
        # Wait for pod to be running
        pod_name = await self._get_pod_name(container_id)
        if not pod_name:
            yield "Error: could not find pod for job"
            return

        try:
            log_stream = self._api.read_namespaced_pod_log(
                pod_name, self._namespace, follow=True, _preload_content=False
            )
            for line in log_stream:
                yield line.decode("utf-8", errors="replace")
        except Exception as e:
            yield f"Error streaming logs: {e}"

    async def collect_result(self, container_id: str) -> ExecutionResult:
        self._init_client()
        # Wait for job completion
        for _ in range(600):  # 10 minute max wait
            job = await asyncio.to_thread(self._batch_api.read_namespaced_job, container_id, self._namespace)
            if job.status.succeeded:
                break
            if job.status.failed:
                break
            await asyncio.sleep(1)

        # Get logs
        pod_name = await self._get_pod_name(container_id)
        output = ""
        if pod_name:
            try:
                output = await asyncio.to_thread(self._api.read_namespaced_pod_log, pod_name, self._namespace)
            except Exception as e:
                output = f"Error reading logs: {e}"

        # Check for OOM
        oom = await self.get_oom_status(container_id)
        if oom:
            return ExecutionResult(output=output, status="oom", error="Pod OOM-killed")

        if job.status.succeeded:
            return ExecutionResult(output=output, status="completed", container_id=container_id)
        return ExecutionResult(output=output, status="failed", error="Job failed", container_id=container_id)

    async def destroy_container(self, container_id: str) -> None:
        self._init_client()

        try:
            await asyncio.to_thread(
                self._batch_api.delete_namespaced_job,
                container_id,
                self._namespace,
                propagation_policy="Foreground",
            )
            logger.info(f"Destroyed K8s job: {container_id}")
        except Exception as e:
            logger.warning(f"Error destroying K8s job {container_id}: {e}")

    async def get_exit_code(self, container_id: str) -> Optional[int]:
        self._init_client()
        pod_name = await self._get_pod_name(container_id)
        if not pod_name:
            return None
        try:
            pod = await asyncio.to_thread(self._api.read_namespaced_pod, pod_name, self._namespace)
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.terminated:
                    return cs.state.terminated.exit_code
        except Exception:
            pass
        return None

    async def get_oom_status(self, container_id: str) -> bool:
        self._init_client()
        pod_name = await self._get_pod_name(container_id)
        if not pod_name:
            return False
        try:
            pod = await asyncio.to_thread(self._api.read_namespaced_pod, pod_name, self._namespace)
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.terminated and cs.state.terminated.reason == "OOMKilled":
                    return True
        except Exception:
            pass
        return False

    async def health_check(self) -> bool:
        try:
            self._init_client()
            await asyncio.to_thread(self._api.list_node, limit=1)
            return True
        except Exception:
            return False

    async def _get_pod_name(self, job_name: str) -> Optional[str]:
        try:
            pods = await asyncio.to_thread(
                self._api.list_namespaced_pod,
                self._namespace,
                label_selector=f"job-name={job_name}",
            )
            if pods.items:
                return pods.items[0].metadata.name
        except Exception:
            pass
        return None
