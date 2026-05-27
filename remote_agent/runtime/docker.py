import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from supervisor.models import ExecutionResult
from remote_agent.runtime.base import ContainerRuntime

logger = logging.getLogger(__name__)


class DockerRuntime(ContainerRuntime):
    """Docker container runtime for single-VM deployments."""

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import docker  # type: ignore[import-untyped]

                self._client = docker.from_env()
            except ImportError:
                raise RuntimeError("docker package required for DockerRuntime")
        return self._client

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
        client = self._get_client()

        kwargs: Dict[str, Any] = {
            "image": image,
            "command": command,
            "environment": env or {},
            "volumes": {workspace_dir: {"bind": "/workspace", "mode": "rw"}},
            "working_dir": "/workspace",
            "detach": True,
            "labels": labels or {},
        }

        if not network_enabled:
            kwargs["network_mode"] = "none"

        if cpu_limit:
            kwargs["nano_cpus"] = int(cpu_limit * 1e9)
        if memory_limit_mb:
            kwargs["mem_limit"] = f"{memory_limit_mb}m"

        container = await asyncio.to_thread(client.containers.run, **kwargs)
        logger.info(f"Created Docker container: {container.id[:12]}")
        return container.id

    async def stream_output(self, container_id: str) -> AsyncGenerator[str, None]:  # type: ignore[override]
        client = self._get_client()
        container = client.containers.get(container_id)
        for line in container.logs(stream=True, follow=True):
            yield line.decode("utf-8", errors="replace")

    async def collect_result(self, container_id: str) -> ExecutionResult:
        client = self._get_client()
        container = client.containers.get(container_id)

        exit_info = await asyncio.to_thread(container.wait)
        exit_code = exit_info.get("StatusCode", -1)
        logs = await asyncio.to_thread(container.logs)
        output = logs.decode("utf-8", errors="replace")

        if exit_code == 137:
            return ExecutionResult(output=output, status="oom", error="Container OOM-killed")

        return ExecutionResult(
            output=output,
            status="completed" if exit_code == 0 else "failed",
            error=f"Exit code: {exit_code}" if exit_code != 0 else None,
            container_id=container_id[:12],
        )

    async def destroy_container(self, container_id: str) -> None:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            await asyncio.to_thread(container.stop, timeout=10)
            await asyncio.to_thread(container.remove, force=True)
            logger.info(f"Destroyed Docker container: {container_id[:12]}")
        except Exception as e:
            logger.warning(f"Error destroying container {container_id[:12]}: {e}")

    async def get_exit_code(self, container_id: str) -> Optional[int]:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.reload()
            return container.attrs.get("State", {}).get("ExitCode")
        except Exception:
            return None

    async def get_oom_status(self, container_id: str) -> bool:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.reload()
            return container.attrs.get("State", {}).get("OOMKilled", False)
        except Exception:
            return False

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            client.ping()
            return True
        except Exception:
            return False
