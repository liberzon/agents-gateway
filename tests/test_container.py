"""Tests for container management: DockerRuntime, KubernetesRuntime, ContainerExecutor."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from supervisor.models import ExecutionResult, JobSpec, WorkerConfig


# ---------------------------------------------------------------------------
# DockerRuntime tests
# ---------------------------------------------------------------------------


class TestDockerRuntimeCreateContainer(unittest.TestCase):
    """Test DockerRuntime.create_container."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_create_container_returns_id(self, mock_get_client: MagicMock) -> None:
        """create_container returns a container ID string."""
        mock_container = MagicMock()
        mock_container.id = "abc123def456"
        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        cid = asyncio.run(
            runtime.create_container(
                image="worker:latest",
                workspace_dir="/tmp/ws",
                command=["echo", "hello"],
            )
        )

        self.assertEqual(cid, "abc123def456")
        mock_client.containers.run.assert_called_once()

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_create_container_with_resource_limits(self, mock_get_client: MagicMock) -> None:
        """create_container passes CPU and memory limits."""
        mock_container = MagicMock()
        mock_container.id = "limited123"
        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        asyncio.run(
            runtime.create_container(
                image="worker:latest",
                workspace_dir="/tmp/ws",
                command=["echo", "hello"],
                cpu_limit=2.0,
                memory_limit_mb=4096,
                network_enabled=False,
            )
        )

        call_kwargs = mock_client.containers.run.call_args[1]
        self.assertEqual(call_kwargs["nano_cpus"], int(2.0 * 1e9))
        self.assertEqual(call_kwargs["mem_limit"], "4096m")
        self.assertEqual(call_kwargs["network_mode"], "none")

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_create_container_network_enabled(self, mock_get_client: MagicMock) -> None:
        """When network_enabled=True, network_mode is not set to 'none'."""
        mock_container = MagicMock()
        mock_container.id = "net123"
        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        asyncio.run(
            runtime.create_container(
                image="worker:latest",
                workspace_dir="/tmp/ws",
                command=["echo", "hello"],
                network_enabled=True,
            )
        )

        call_kwargs = mock_client.containers.run.call_args[1]
        self.assertNotIn("network_mode", call_kwargs)


class TestDockerRuntimeCollectResult(unittest.TestCase):
    """Test DockerRuntime.collect_result."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_collect_result_success(self, mock_get_client: MagicMock) -> None:
        """collect_result returns completed status on exit code 0."""
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"Task completed successfully"
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.collect_result("abc123"))

        self.assertEqual(result.status, "completed")
        self.assertIn("Task completed", result.output)

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_collect_result_oom_exit_137(self, mock_get_client: MagicMock) -> None:
        """collect_result detects OOM from exit code 137."""
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 137}
        mock_container.logs.return_value = b"Killed"
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.collect_result("oom123"))

        self.assertEqual(result.status, "oom")
        self.assertIn("OOM", result.error or "")

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_collect_result_failure(self, mock_get_client: MagicMock) -> None:
        """collect_result returns failed status on non-zero, non-OOM exit code."""
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.return_value = b"Error"
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.collect_result("fail123"))

        self.assertEqual(result.status, "failed")


class TestDockerRuntimeOOMDetection(unittest.TestCase):
    """Test Docker OOM detection via OOMKilled flag."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_oom_status_true(self, mock_get_client: MagicMock) -> None:
        """get_oom_status returns True when OOMKilled is set."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"OOMKilled": True}}
        mock_container.reload.return_value = None
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.get_oom_status("oom-container"))
        self.assertTrue(result)

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_oom_status_false(self, mock_get_client: MagicMock) -> None:
        """get_oom_status returns False when OOMKilled is not set."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"OOMKilled": False}}
        mock_container.reload.return_value = None
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.get_oom_status("ok-container"))
        self.assertFalse(result)


class TestDockerRuntimeDestroy(unittest.TestCase):
    """Test DockerRuntime.destroy_container."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_destroy_container(self, mock_get_client: MagicMock) -> None:
        """destroy_container stops and removes the container."""
        mock_container = MagicMock()
        mock_container.stop.return_value = None
        mock_container.remove.return_value = None
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        asyncio.run(runtime.destroy_container("del123"))
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()


class TestDockerRuntimeHealthCheck(unittest.TestCase):
    """Test DockerRuntime.health_check."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_health_check_success(self, mock_get_client: MagicMock) -> None:
        """health_check returns True when Docker daemon is reachable."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.health_check())
        self.assertTrue(result)

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_health_check_failure(self, mock_get_client: MagicMock) -> None:
        """health_check returns False when Docker daemon is unreachable."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        result = asyncio.run(runtime.health_check())
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# KubernetesRuntime tests
# ---------------------------------------------------------------------------


class TestKubernetesRuntimeCreateContainer(unittest.TestCase):
    """Test KubernetesRuntime.create_container."""

    @patch("remote_agent.runtime.kubernetes.KubernetesRuntime._init_client")
    def test_create_k8s_job(self, mock_init: MagicMock) -> None:
        """create_container creates a K8s Job and returns job name."""
        # Mock the kubernetes client module so the import inside create_container works
        mock_k8s = MagicMock()
        with patch.dict(
            "sys.modules", {"kubernetes": MagicMock(), "kubernetes.client": mock_k8s, "kubernetes.config": MagicMock()}
        ):
            from remote_agent.runtime.kubernetes import KubernetesRuntime

            runtime = KubernetesRuntime(namespace="test-ns")
            mock_init.return_value = None

            # Mock batch API
            runtime._batch_api = MagicMock()
            runtime._batch_api.create_namespaced_job.return_value = None

            loop = asyncio.new_event_loop()
            try:
                job_name = loop.run_until_complete(
                    runtime.create_container(
                        image="worker:latest",
                        workspace_dir="/tmp/ws",
                        command=["echo", "hello"],
                        cpu_limit=1.0,
                        memory_limit_mb=2048,
                    )
                )
            finally:
                loop.close()

            self.assertTrue(job_name.startswith("worker-"))
            runtime._batch_api.create_namespaced_job.assert_called_once()


class TestKubernetesRuntimeOOMDetection(unittest.TestCase):
    """Test K8s OOM detection."""

    @patch("remote_agent.runtime.kubernetes.KubernetesRuntime._init_client")
    def test_oom_detected_from_pod_status(self, mock_init: MagicMock) -> None:
        """get_oom_status detects OOMKilled from container status."""
        with patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(), "kubernetes.client": MagicMock(), "kubernetes.config": MagicMock()},
        ):
            from remote_agent.runtime.kubernetes import KubernetesRuntime

            runtime = KubernetesRuntime(namespace="test-ns")
            mock_init.return_value = None
            runtime._api = MagicMock()

            # Mock pod list
            mock_pod = MagicMock()
            mock_pod.metadata.name = "worker-pod-1"

            # Mock container status with OOMKilled
            mock_cs = MagicMock()
            mock_cs.state.terminated.reason = "OOMKilled"
            mock_pod.status.container_statuses = [mock_cs]

            mock_pods = MagicMock()
            mock_pods.items = [mock_pod]
            runtime._api.list_namespaced_pod.return_value = mock_pods
            runtime._api.read_namespaced_pod.return_value = mock_pod

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(runtime.get_oom_status("worker-test"))
            finally:
                loop.close()
            self.assertTrue(result)


class TestKubernetesRuntimePodLogStreaming(unittest.TestCase):
    """Test K8s pod log streaming."""

    @patch("remote_agent.runtime.kubernetes.KubernetesRuntime._init_client")
    def test_stream_output_returns_lines(self, mock_init: MagicMock) -> None:
        """stream_output yields log lines from the pod."""
        with patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(), "kubernetes.client": MagicMock(), "kubernetes.config": MagicMock()},
        ):
            from remote_agent.runtime.kubernetes import KubernetesRuntime

            runtime = KubernetesRuntime(namespace="test-ns")
            mock_init.return_value = None
            runtime._api = MagicMock()

            # Mock pod discovery
            mock_pod = MagicMock()
            mock_pod.metadata.name = "worker-pod-1"
            mock_pods = MagicMock()
            mock_pods.items = [mock_pod]
            runtime._api.list_namespaced_pod.return_value = mock_pods

            # Mock log stream
            runtime._api.read_namespaced_pod_log.return_value = [b"line1\n", b"line2\n"]

            lines: list[str] = []

            async def collect() -> None:
                async for line in runtime.stream_output("worker-test"):
                    lines.append(line)

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(collect())
            finally:
                loop.close()
            self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# ContainerExecutor tests
# ---------------------------------------------------------------------------


class TestContainerExecutorLifecycle(unittest.TestCase):
    """Test ContainerExecutor full lifecycle."""

    def test_full_lifecycle(self) -> None:
        """Execute: workspace setup -> spawn -> collect -> cleanup."""
        mock_runtime = MagicMock()
        mock_runtime.create_container = AsyncMock(return_value="container-123")
        mock_runtime.collect_result = AsyncMock(
            return_value=ExecutionResult(output="Done", status="completed", container_id="container-123")
        )
        mock_runtime.get_oom_status = AsyncMock(return_value=False)
        mock_runtime.destroy_container = AsyncMock()

        from remote_agent.executor import ContainerExecutor

        executor = ContainerExecutor(runtime=mock_runtime, worker_image="worker:latest")

        worker_config = WorkerConfig()
        result = asyncio.run(executor.execute(prompt="Fix the bug", worker_config=worker_config))

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.container_id, "container-123")
        mock_runtime.create_container.assert_called_once()
        mock_runtime.collect_result.assert_called_once()
        mock_runtime.destroy_container.assert_called_once()

    def test_lifecycle_with_oom(self) -> None:
        """Execute detects OOM status and reports it."""
        mock_runtime = MagicMock()
        mock_runtime.create_container = AsyncMock(return_value="oom-container")
        mock_runtime.collect_result = AsyncMock(
            return_value=ExecutionResult(output="", status="failed", container_id="oom-container")
        )
        mock_runtime.get_oom_status = AsyncMock(return_value=True)
        mock_runtime.destroy_container = AsyncMock()

        from remote_agent.executor import ContainerExecutor

        executor = ContainerExecutor(runtime=mock_runtime, worker_image="worker:latest")

        worker_config = WorkerConfig()
        result = asyncio.run(executor.execute(prompt="Big task", worker_config=worker_config))

        self.assertEqual(result.status, "oom")

    def test_lifecycle_with_job_spec_limits(self) -> None:
        """Execute uses JobSpec execution limits for resource allocation."""
        mock_runtime = MagicMock()
        mock_runtime.create_container = AsyncMock(return_value="limited-container")
        mock_runtime.collect_result = AsyncMock(
            return_value=ExecutionResult(output="OK", status="completed", container_id="limited-container")
        )
        mock_runtime.get_oom_status = AsyncMock(return_value=False)
        mock_runtime.destroy_container = AsyncMock()

        from remote_agent.executor import ContainerExecutor

        executor = ContainerExecutor(runtime=mock_runtime, worker_image="worker:latest")

        from supervisor.models import ExecutionLimits

        job_spec = JobSpec(
            job_type="coding",
            execution_limits=ExecutionLimits(max_memory_mb=8192, max_cpus=4.0, network_access=True),
        )
        worker_config = WorkerConfig()

        result = asyncio.run(executor.execute(prompt="Task", worker_config=worker_config, job_spec=job_spec))

        self.assertEqual(result.status, "completed")

        # Verify resource limits were passed
        create_call_kwargs = mock_runtime.create_container.call_args[1]
        self.assertEqual(create_call_kwargs["memory_limit_mb"], 8192)
        self.assertEqual(create_call_kwargs["cpu_limit"], 4.0)
        self.assertTrue(create_call_kwargs["network_enabled"])

    def test_lifecycle_error_still_cleans_up(self) -> None:
        """When container execution raises, cleanup still occurs."""
        mock_runtime = MagicMock()
        mock_runtime.create_container = AsyncMock(return_value="error-container")
        mock_runtime.collect_result = AsyncMock(side_effect=Exception("Runtime error"))
        mock_runtime.get_oom_status = AsyncMock(return_value=False)
        mock_runtime.destroy_container = AsyncMock()

        from remote_agent.executor import ContainerExecutor

        executor = ContainerExecutor(runtime=mock_runtime, worker_image="worker:latest")

        worker_config = WorkerConfig()
        result = asyncio.run(executor.execute(prompt="Will fail", worker_config=worker_config))

        self.assertEqual(result.status, "failed")
        mock_runtime.destroy_container.assert_called_once()


if __name__ == "__main__":
    unittest.main()
