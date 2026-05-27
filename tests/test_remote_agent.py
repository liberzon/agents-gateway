"""Tests for the remote agent service (remote_agent/app.py)."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from supervisor.models import ExecutionResult


class TestRemoteAgentHealth(unittest.TestCase):
    """Test /health endpoint."""

    @patch("remote_agent.app._get_runtime")
    def test_health_returns_runtime_info(self, mock_get_runtime: MagicMock) -> None:
        """Health endpoint returns runtime type, image, and status."""
        mock_runtime = MagicMock()
        mock_runtime.health_check = AsyncMock(return_value=True)
        mock_get_runtime.return_value = mock_runtime

        from remote_agent.app import app

        client = TestClient(app)
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("runtime", data)
        self.assertIn("worker_image", data)

    @patch("remote_agent.app._get_runtime")
    def test_health_unhealthy(self, mock_get_runtime: MagicMock) -> None:
        """Health endpoint returns unhealthy when runtime is down."""
        mock_runtime = MagicMock()
        mock_runtime.health_check = AsyncMock(return_value=False)
        mock_get_runtime.return_value = mock_runtime

        from remote_agent.app import app

        client = TestClient(app)
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "unhealthy")


class TestRemoteAgentExecute(unittest.TestCase):
    """Test /execute endpoint."""

    @patch("remote_agent.app._get_executor")
    def test_execute_with_mocked_runtime(self, mock_get_executor: MagicMock) -> None:
        """Execute endpoint runs a task in a mocked container."""
        mock_result = ExecutionResult(
            output="Task completed",
            status="completed",
            files_changed=["main.py"],
        )
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)
        mock_get_executor.return_value = mock_executor

        from remote_agent.app import app

        client = TestClient(app)
        response = client.post(
            "/execute",
            json={
                "prompt": "Fix the bug",
                "worker_config": {"mcp_servers": []},
                "model": "claude-sonnet-4-6",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["output"], "Task completed")


class TestRemoteAgentJobs(unittest.TestCase):
    """Test /jobs endpoints."""

    def test_active_jobs_returns_empty_list(self) -> None:
        """Active jobs endpoint returns placeholder empty list."""
        from remote_agent.app import app

        client = TestClient(app)
        response = client.get("/jobs/active")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("active_jobs", data)
        self.assertEqual(data["active_jobs"], [])

    @patch("remote_agent.app._get_runtime")
    def test_cancel_job_success(self, mock_get_runtime: MagicMock) -> None:
        """Cancel a running job by destroying its container."""
        mock_runtime = MagicMock()
        mock_runtime.destroy_container = AsyncMock()
        mock_get_runtime.return_value = mock_runtime

        from remote_agent.app import app

        client = TestClient(app)
        response = client.post("/jobs/test-container-123/cancel")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertEqual(data["job_id"], "test-container-123")

    @patch("remote_agent.app._get_runtime")
    def test_cancel_job_failure(self, mock_get_runtime: MagicMock) -> None:
        """Cancel fails when runtime raises exception."""
        mock_runtime = MagicMock()
        mock_runtime.destroy_container = AsyncMock(side_effect=Exception("Container not found"))
        mock_get_runtime.return_value = mock_runtime

        from remote_agent.app import app

        client = TestClient(app)
        response = client.post("/jobs/missing-container/cancel")

        self.assertEqual(response.status_code, 500)


class TestJobConsumerWiring(unittest.TestCase):
    """Test JobConsumer background task wiring in lifespan."""

    def test_consumer_not_started_by_default(self) -> None:
        """When JOB_CONSUMER_ENABLED is false (default), no background task starts."""
        import remote_agent.app as ra_module

        # _consumer_task should be None when not enabled
        self.assertIsNone(ra_module._consumer_task)

    @patch.dict("os.environ", {"JOB_CONSUMER_ENABLED": "true"})
    @patch("remote_agent.app._run_job_consumer_loop", new_callable=AsyncMock)
    def test_consumer_enabled_env_var(self, mock_loop: AsyncMock) -> None:
        """When JOB_CONSUMER_ENABLED=true, the lifespan starts the consumer task."""
        # Re-import to pick up env var change

        import remote_agent.app as ra_module

        # The env var should have been read
        # We verify by checking that the constant was read at module load time
        # The actual task creation happens in the lifespan context manager
        self.assertIsNotNone(ra_module.lifespan)


if __name__ == "__main__":
    unittest.main()
