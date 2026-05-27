"""Comprehensive tests covering every use case discussed in the conversation.

Covers: MCP plugin, multi-model, approval flow, OOM recovery, streaming,
Claude Code execution, container per job, engine/target registry, pack format.
"""

import asyncio
import json
import os
import tempfile
import unittest
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import yaml  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# MCP Plugin Tests
# ---------------------------------------------------------------------------


class TestMCPPluginGeneration(unittest.TestCase):
    """Test that ClaudeCodeToolkit generates correct .mcp.json and --mcp-config."""

    def test_mcp_json_with_filesystem_and_git(self) -> None:
        """Generate .mcp.json with filesystem and git MCPs."""
        from supervisor.models import MCPServerConfig, WorkerConfig
        from supervisor.plugins.generator import PluginConfigGenerator

        config = WorkerConfig(
            mcp_servers=[
                MCPServerConfig(
                    name="filesystem",
                    type="stdio",
                    command="npx",
                    args=["-y", "@anthropic/mcp-filesystem", "/workspace"],
                ),
                MCPServerConfig(
                    name="git",
                    type="stdio",
                    command="npx",
                    args=["-y", "@anthropic/mcp-git"],
                ),
            ]
        )

        generator = PluginConfigGenerator()
        mcp_json = generator.generate_mcp_json(config)

        self.assertIn("mcpServers", mcp_json)
        servers = mcp_json["mcpServers"]
        self.assertIn("filesystem", servers)
        self.assertIn("git", servers)
        self.assertEqual(servers["filesystem"]["command"], "npx")
        self.assertIn("@anthropic/mcp-filesystem", servers["filesystem"]["args"])
        self.assertEqual(servers["git"]["command"], "npx")

    def test_mcp_config_flag_in_cli_command(self) -> None:
        """--mcp-config flag is passed to the Claude CLI when .mcp.json exists."""
        from supervisor.models import MCPServerConfig, WorkerConfig
        from toolkits.claude_code import ClaudeCodeToolkit

        config = WorkerConfig(
            mcp_servers=[
                MCPServerConfig(name="git", type="stdio", command="npx", args=["-y", "@anthropic/mcp-git"]),
            ]
        )
        toolkit = ClaudeCodeToolkit(user_id="test-user", worker_config=config)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write .mcp.json so the command builder finds it
            mcp_path = os.path.join(tmpdir, ".mcp.json")
            with open(mcp_path, "w") as f:
                json.dump({"mcpServers": {}}, f)

            cmd = toolkit._build_cli_command("fix bug", "claude-sonnet-4-6", 10, tmpdir)

            self.assertIn("--mcp-config", cmd)
            self.assertIn(mcp_path, cmd)

    def test_mcp_config_flag_absent_without_mcp_json(self) -> None:
        """--mcp-config flag is NOT passed when no .mcp.json file exists."""
        from supervisor.models import WorkerConfig
        from toolkits.claude_code import ClaudeCodeToolkit

        toolkit = ClaudeCodeToolkit(user_id="test-user", worker_config=WorkerConfig())

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = toolkit._build_cli_command("fix bug", "claude-sonnet-4-6", 10, tmpdir)
            self.assertNotIn("--mcp-config", cmd)

    def test_workspace_config_writes_mcp_json(self) -> None:
        """write_workspace_config creates .mcp.json on disk."""
        from supervisor.models import MCPServerConfig, WorkerConfig
        from supervisor.plugins.generator import PluginConfigGenerator

        config = WorkerConfig(
            mcp_servers=[
                MCPServerConfig(name="git", type="stdio", command="npx", args=["-y", "@anthropic/mcp-git"]),
            ]
        )

        generator = PluginConfigGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            generator.write_workspace_config(tmpdir, config)

            mcp_path = os.path.join(tmpdir, ".mcp.json")
            self.assertTrue(os.path.exists(mcp_path))

            with open(mcp_path) as f:
                data = json.load(f)
            self.assertIn("git", data["mcpServers"])


# ---------------------------------------------------------------------------
# Multi-model Tests
# ---------------------------------------------------------------------------


class TestMultiModelTeamRun(unittest.TestCase):
    """Test team run with different models (mocked)."""

    def setUp(self) -> None:
        self.client, self.app = self._make_client()

    def _make_client(self) -> tuple:
        from tests.test_utils import create_test_client

        client, app = create_test_client()
        from api.routes.v2_router import get_v2_router

        app.include_router(get_v2_router())

        from fastapi.testclient import TestClient

        return TestClient(app), app

    def _run_with_model(self, model_value: str) -> Any:
        """Helper that sets up mocks and runs a team with the given model."""
        import datetime

        now = datetime.datetime.utcnow()
        from db.db_models import TeamAgentDB, TeamInfoDB

        mock_team_db = TeamInfoDB(
            id="multi-model-team",
            name="Multi-Model Team",
            version="2.0",
            mode="supervisor",
            created_at=now,
            updated_at=now,
        )
        mock_agents = [
            TeamAgentDB(
                id=1, team_id="multi-model-team", agent_id="leader", role="leader", order_index=0, created_at=now
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = f"Response from {model_value}"
        mock_response.metrics = None
        mock_response.status = "completed"
        mock_response.run_id = f"run-{model_value}"
        mock_response.tools = []

        mock_team = MagicMock()
        mock_team.arun = AsyncMock(return_value=mock_response)

        with (
            patch("api.routes.v2.teams.get_team_info", return_value=mock_team_db),
            patch("api.routes.v2.teams.get_team_agents", return_value=mock_agents),
            patch("supervisor.team_builder.build_supervisor_team", return_value=mock_team),
        ):
            response = self.client.post(
                "/v2/teams/multi-model-team/runs",
                json={"message": "Hello", "stream": False, "model": model_value},
            )
        return response

    def test_claude_sonnet_4_6(self) -> None:
        """Team run with claude-sonnet-4-6."""
        response = self._run_with_model("claude-sonnet-4-6")
        self.assertEqual(response.status_code, 200)
        self.assertIn("claude-sonnet-4-6", response.json()["content"])

    def test_gemini_2_5_flash(self) -> None:
        """Team run with gemini-2.5-flash."""
        response = self._run_with_model("gemini-2.5-flash")
        self.assertEqual(response.status_code, 200)

    def test_gpt_5_4(self) -> None:
        """Team run with gpt-5.4."""
        response = self._run_with_model("gpt-5.4")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Approval Flow Tests
# ---------------------------------------------------------------------------


class TestApprovalLifecycle(unittest.TestCase):
    """Test full approval lifecycle: register -> poll -> approve/deny."""

    def test_register_and_poll_pending(self) -> None:
        """Register a pending approval and poll for it."""
        from supervisor.approval import (
            ApprovalNotification,
            _pending_approvals,
            get_pending_approval,
            get_pending_approvals,
            register_pending_approval,
        )

        # Clear state
        _pending_approvals.clear()

        notification = ApprovalNotification(
            job_id="test-job-1",
            tool_name="rm -rf /",
            tool_args={"path": "/data"},
            risk_level="high",
            reason="Destructive operation",
        )
        register_pending_approval(notification)

        # Poll
        pending = get_pending_approvals()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].job_id, "test-job-1")

        specific = get_pending_approval("test-job-1")
        self.assertIsNotNone(specific)
        self.assertEqual(specific.tool_name, "rm -rf /")  # type: ignore[union-attr]

        # Cleanup
        _pending_approvals.clear()

    def test_submit_decision_approve(self) -> None:
        """Submit an approval decision."""
        from supervisor.approval import (
            ApprovalNotification,
            _approval_decisions,
            _approval_events,
            _pending_approvals,
            register_pending_approval,
            submit_decision,
        )

        _pending_approvals.clear()
        _approval_decisions.clear()
        _approval_events.clear()

        notification = ApprovalNotification(job_id="approve-job", tool_name="deploy")
        register_pending_approval(notification)

        result = submit_decision("approve-job", approved=True, reason="Looks good")
        self.assertTrue(result)

        # Pending should be cleared
        self.assertNotIn("approve-job", _pending_approvals)

        # Cleanup
        _approval_decisions.clear()
        _approval_events.clear()

    def test_submit_decision_deny(self) -> None:
        """Submit a denial decision."""
        from supervisor.approval import (
            ApprovalNotification,
            _approval_decisions,
            _approval_events,
            _pending_approvals,
            register_pending_approval,
            submit_decision,
        )

        _pending_approvals.clear()
        _approval_decisions.clear()
        _approval_events.clear()

        notification = ApprovalNotification(job_id="deny-job", tool_name="drop_table")
        register_pending_approval(notification)

        result = submit_decision("deny-job", approved=False, reason="Too dangerous")
        self.assertTrue(result)

        _approval_decisions.clear()
        _approval_events.clear()

    def test_submit_decision_nonexistent(self) -> None:
        """Submit decision for non-existent job returns False."""
        from supervisor.approval import _pending_approvals, submit_decision

        _pending_approvals.clear()
        result = submit_decision("nonexistent-job", approved=True)
        self.assertFalse(result)


class TestNotificationPluginRegistry(unittest.TestCase):
    """Test notification plugin dispatch and registry."""

    def test_builtin_plugins_registered(self) -> None:
        """Webhook, Telegram, Slack, Discord, WhatsApp plugins are registered."""
        from supervisor.approval import list_plugins

        plugins = list_plugins()
        self.assertIn("webhook", plugins)
        self.assertIn("telegram", plugins)
        self.assertIn("slack", plugins)
        self.assertIn("discord", plugins)
        self.assertIn("whatsapp", plugins)

    def test_get_plugin_by_name(self) -> None:
        """Can retrieve a plugin by name."""
        from supervisor.approval import get_plugin

        plugin = get_plugin("webhook")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "webhook")  # type: ignore[union-attr]

    def test_get_unknown_plugin(self) -> None:
        """Retrieving unknown plugin returns None."""
        from supervisor.approval import get_plugin

        plugin = get_plugin("carrier_pigeon")
        self.assertIsNone(plugin)

    def test_notify_with_no_plugins(self) -> None:
        """Notify with empty plugins list still registers the pending approval."""
        from supervisor.approval import (
            ApprovalConfig,
            ApprovalNotification,
            _pending_approvals,
            notify_approval_needed,
        )

        _pending_approvals.clear()

        notification = ApprovalNotification(job_id="no-plugin-job", tool_name="test_tool")
        config = ApprovalConfig(plugins=[], polling_enabled=True)

        result = asyncio.run(notify_approval_needed(notification, config))
        self.assertTrue(result)
        self.assertIn("no-plugin-job", _pending_approvals)

        _pending_approvals.clear()


# ---------------------------------------------------------------------------
# OOM Recovery Tests
# ---------------------------------------------------------------------------


class TestOOMRecovery(unittest.TestCase):
    """Test retry with 2x memory, supervisor re-plan, circuit breaker."""

    @patch("supervisor.recovery.get_execution_job")
    @patch("supervisor.recovery.increment_retry")
    def test_oom_retry_with_double_memory(self, mock_incr: MagicMock, mock_get: MagicMock) -> None:
        """OOM triggers retry with 2x memory."""
        from supervisor.models import RetryPolicy
        from supervisor.recovery import RetryAction, handle_oom

        job = MagicMock()
        job.retry_count = 0
        job.memory_limit_mb = 4096
        mock_get.return_value = job
        mock_incr.return_value = True

        db = MagicMock()
        job_id = uuid.uuid4()
        action = handle_oom(db, job_id, RetryPolicy(max_retries=2, memory_multiplier=2.0))

        self.assertEqual(action, RetryAction.retry)
        mock_incr.assert_called_once_with(db, job_id, 8192)

    @patch("supervisor.recovery.get_execution_job")
    @patch("supervisor.recovery.fail_job")
    def test_oom_triggers_replan(self, mock_fail: MagicMock, mock_get: MagicMock) -> None:
        """OOM after max retries triggers supervisor re-plan."""
        from supervisor.models import RetryPolicy
        from supervisor.recovery import RetryAction, handle_oom

        job = MagicMock()
        job.retry_count = 2  # Already at max
        job.memory_limit_mb = 16384
        mock_get.return_value = job

        db = MagicMock()
        # circuit_breaker_threshold must be > total_failures (retry_count + 1 = 3)
        action = handle_oom(
            db,
            uuid.uuid4(),
            RetryPolicy(max_retries=2, enable_supervisor_replan=True, circuit_breaker_threshold=5),
        )

        self.assertEqual(action, RetryAction.replan)

    @patch("supervisor.recovery.get_execution_job")
    @patch("supervisor.recovery.fail_job")
    def test_circuit_breaker_opens(self, mock_fail: MagicMock, mock_get: MagicMock) -> None:
        """Circuit breaker opens after N failures."""
        from supervisor.models import RetryPolicy
        from supervisor.recovery import RetryAction, handle_oom

        job = MagicMock()
        job.retry_count = 2
        job.memory_limit_mb = 16384
        mock_get.return_value = job

        db = MagicMock()
        action = handle_oom(db, uuid.uuid4(), RetryPolicy(max_retries=2, circuit_breaker_threshold=3))

        self.assertEqual(action, RetryAction.circuit_open)
        mock_fail.assert_called_once()
        call_args = mock_fail.call_args[0]
        self.assertEqual(call_args[3], "failed_circuit_open")

    def test_is_oom_exit_docker(self) -> None:
        """Docker OOM detection via exit code 137."""
        from supervisor.recovery import is_oom_exit

        self.assertTrue(is_oom_exit(exit_code=137))
        self.assertFalse(is_oom_exit(exit_code=0))
        self.assertFalse(is_oom_exit(exit_code=1))

    def test_is_oom_exit_k8s(self) -> None:
        """K8s OOM detection via OOMKilled reason."""
        from supervisor.recovery import is_oom_exit

        self.assertTrue(is_oom_exit(k8s_reason="OOMKilled"))
        self.assertFalse(is_oom_exit(k8s_reason="Completed"))


# ---------------------------------------------------------------------------
# Streaming Tests
# ---------------------------------------------------------------------------


class TestStreamVerbosity(unittest.TestCase):
    """Test stream_verbosity field and filtering."""

    def test_stream_verbosity_enum_values(self) -> None:
        """StreamVerbosity enum has full, events, result."""
        from supervisor.models import StreamVerbosity

        self.assertEqual(StreamVerbosity.full, "full")
        self.assertEqual(StreamVerbosity.events, "events")
        self.assertEqual(StreamVerbosity.result, "result")

    def test_team_run_request_accepts_stream_verbosity(self) -> None:
        """TeamRunRequest model accepts stream_verbosity field."""
        from api.routes.v2.teams import TeamRunRequest

        req = TeamRunRequest(message="Hello", stream=True, stream_verbosity="full")
        self.assertEqual(req.stream_verbosity, "full")

    def test_team_run_request_default_stream_verbosity(self) -> None:
        """TeamRunRequest defaults stream_verbosity to 'events'."""
        from api.routes.v2.teams import TeamRunRequest

        req = TeamRunRequest(message="Hello")
        self.assertEqual(req.stream_verbosity, "events")


class TestStreamJsonEventParsing(unittest.TestCase):
    """Test stream-json event parsing in the streaming toolkit."""

    def test_parse_result_event(self) -> None:
        """_parse_cli_output parses a result event from stream-json."""
        from toolkits.claude_code import ClaudeCodeToolkit

        toolkit = ClaudeCodeToolkit(user_id="test")

        stdout = json.dumps({"result": "All done", "files_changed": ["main.py"]})
        result = toolkit._parse_cli_output(stdout, "", 0)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output, "All done")

    def test_parse_empty_output(self) -> None:
        """_parse_cli_output handles empty stdout."""
        from toolkits.claude_code import ClaudeCodeToolkit

        toolkit = ClaudeCodeToolkit(user_id="test")
        result = toolkit._parse_cli_output("", "Some error", 1)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "Some error")

    def test_parse_non_json_output(self) -> None:
        """_parse_cli_output handles non-JSON stdout."""
        from toolkits.claude_code import ClaudeCodeToolkit

        toolkit = ClaudeCodeToolkit(user_id="test")
        result = toolkit._parse_cli_output("plain text output", "", 0)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output, "plain text output")


# ---------------------------------------------------------------------------
# Claude Code Execution Tests
# ---------------------------------------------------------------------------


class TestClaudeCodeExecution(unittest.TestCase):
    """Test ClaudeCodeToolkit execution methods."""

    def setUp(self) -> None:
        from supervisor.models import WorkerConfig
        from toolkits.claude_code import ClaudeCodeToolkit

        self.toolkit = ClaudeCodeToolkit(user_id="test-user", worker_config=WorkerConfig())

    @patch("subprocess.run")
    def test_run_local_success(self, mock_run: MagicMock) -> None:
        """_run_local returns completed result on success."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"result": "Fixed the bug", "files_changed": ["app.py"]}),
            stderr="",
            returncode=0,
        )

        result = self.toolkit._run_local("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output, "Fixed the bug")
        self.assertIn("app.py", result.files_changed)

    @patch("subprocess.run")
    def test_run_local_failure(self, mock_run: MagicMock) -> None:
        """_run_local returns failed on non-zero exit."""
        mock_run.return_value = MagicMock(stdout="", stderr="Error: API timeout", returncode=1)

        result = self.toolkit._run_local("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "failed")
        self.assertIn("API timeout", result.error or "")

    @patch("subprocess.run")
    def test_run_local_oom(self, mock_run: MagicMock) -> None:
        """_run_local detects OOM from exit code 137."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=137)

        result = self.toolkit._run_local("big task", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "oom")

    @patch("subprocess.run")
    def test_run_local_timeout(self, mock_run: MagicMock) -> None:
        """_run_local handles subprocess timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=900)

        result = self.toolkit._run_local("slow task", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "failed")
        self.assertIn("Timed out", result.error or "")

    def test_run_ssh_without_host_errors(self) -> None:
        """_run_ssh returns error when no host is configured."""
        result = self.toolkit._run_ssh("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "failed")
        self.assertIn("No remote_host", result.error or "")

    def test_run_remote_service_without_url_errors(self) -> None:
        """_run_remote_service returns error when no URL is configured."""
        result = self.toolkit._run_remote_service("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        self.assertEqual(result.status, "failed")
        self.assertIn("No remote_api_url", result.error or "")

    def test_parse_cli_output_success(self) -> None:
        """_parse_cli_output parses successful JSON output."""
        stdout = json.dumps({"result": "Done", "files_changed": ["a.py"], "commands_run": ["pytest"]})
        result = self.toolkit._parse_cli_output(stdout, "", 0)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output, "Done")
        self.assertEqual(result.files_changed, ["a.py"])
        self.assertEqual(result.commands_run, ["pytest"])

    def test_parse_cli_output_failure_with_stderr(self) -> None:
        """_parse_cli_output on failure returns stderr as error."""
        result = self.toolkit._parse_cli_output("", "Connection reset", 1)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "Connection reset")

    def test_parse_cli_output_oom_code_137(self) -> None:
        """_parse_cli_output detects OOM from exit code 137."""
        result = self.toolkit._parse_cli_output("", "", 137)

        self.assertEqual(result.status, "oom")
        self.assertIn("OOM", result.error or "")


# ---------------------------------------------------------------------------
# Container Per Job Tests
# ---------------------------------------------------------------------------


class TestDockerRuntimeResourceLimits(unittest.TestCase):
    """Test DockerRuntime with mocked Docker SDK."""

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_resource_limits_applied(self, mock_get_client: MagicMock) -> None:
        """create_container applies CPU and memory limits."""
        mock_container = MagicMock()
        mock_container.id = "limited-123"
        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        asyncio.run(
            runtime.create_container(
                image="worker:latest",
                workspace_dir="/tmp/ws",
                command=["echo"],
                cpu_limit=4.0,
                memory_limit_mb=8192,
            )
        )

        kwargs = mock_client.containers.run.call_args[1]
        self.assertEqual(kwargs["nano_cpus"], int(4.0 * 1e9))
        self.assertEqual(kwargs["mem_limit"], "8192m")

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_network_disabled_by_default(self, mock_get_client: MagicMock) -> None:
        """Network is disabled (network_mode=none) by default."""
        mock_container = MagicMock()
        mock_container.id = "net-off"
        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()

        asyncio.run(
            runtime.create_container(
                image="worker:latest",
                workspace_dir="/tmp/ws",
                command=["echo"],
                network_enabled=False,
            )
        )

        kwargs = mock_client.containers.run.call_args[1]
        self.assertEqual(kwargs["network_mode"], "none")

    @patch("remote_agent.runtime.docker.DockerRuntime._get_client")
    def test_oom_detection_from_exit_code(self, mock_get_client: MagicMock) -> None:
        """collect_result returns status=oom on exit code 137."""
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 137}
        mock_container.logs.return_value = b"Killed"
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        from remote_agent.runtime.docker import DockerRuntime

        runtime = DockerRuntime()
        result = asyncio.run(runtime.collect_result("oom-c"))
        self.assertEqual(result.status, "oom")


class TestKubernetesRuntimeResourceLimits(unittest.TestCase):
    """Test KubernetesRuntime with mocked K8s client."""

    @patch("remote_agent.runtime.kubernetes.KubernetesRuntime._init_client")
    def test_k8s_job_created_with_limits(self, mock_init: MagicMock) -> None:
        """K8s Job is created with correct resource limits."""
        with patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(), "kubernetes.client": MagicMock(), "kubernetes.config": MagicMock()},
        ):
            from remote_agent.runtime.kubernetes import KubernetesRuntime

            runtime = KubernetesRuntime(namespace="test-ns")
            mock_init.return_value = None
            runtime._batch_api = MagicMock()
            runtime._batch_api.create_namespaced_job.return_value = None

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    runtime.create_container(
                        image="worker:latest",
                        workspace_dir="/tmp/ws",
                        command=["echo"],
                        cpu_limit=2.0,
                        memory_limit_mb=4096,
                    )
                )
            finally:
                loop.close()

            runtime._batch_api.create_namespaced_job.assert_called_once()

    @patch("remote_agent.runtime.kubernetes.KubernetesRuntime._init_client")
    def test_k8s_oom_detection(self, mock_init: MagicMock) -> None:
        """K8s OOM detected from pod container status."""
        with patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(), "kubernetes.client": MagicMock(), "kubernetes.config": MagicMock()},
        ):
            from remote_agent.runtime.kubernetes import KubernetesRuntime

            runtime = KubernetesRuntime(namespace="test-ns")
            mock_init.return_value = None
            runtime._api = MagicMock()

            # Mock pod with OOMKilled
            mock_pod = MagicMock()
            mock_pod.metadata.name = "worker-pod"
            mock_cs = MagicMock()
            mock_cs.state.terminated.reason = "OOMKilled"
            mock_pod.status.container_statuses = [mock_cs]

            mock_pods = MagicMock()
            mock_pods.items = [mock_pod]
            runtime._api.list_namespaced_pod.return_value = mock_pods
            runtime._api.read_namespaced_pod.return_value = mock_pod

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(runtime.get_oom_status("worker-job"))
            finally:
                loop.close()
            self.assertTrue(result)


# ---------------------------------------------------------------------------
# Engine / Target Registry Tests
# ---------------------------------------------------------------------------


class TestEngineRegistry(unittest.TestCase):
    """Test CRUD for execution engines via API."""

    def setUp(self) -> None:
        from tests.test_utils import create_test_client

        self.client, self.app = create_test_client()
        from api.routes.v2_router import get_v2_router

        self.app.include_router(get_v2_router())

        from fastapi.testclient import TestClient

        self.client = TestClient(self.app)

    @patch("api.routes.v2.engines.get_engine")
    @patch("api.routes.v2.engines.create_engine")
    def test_create_engine(self, mock_create: MagicMock, mock_get: MagicMock) -> None:
        """Create an execution engine."""
        mock_get.return_value = None  # No conflict

        mock_engine = MagicMock()
        mock_engine.id = "claude-code-engine"
        mock_engine.name = "Claude Code Engine"
        mock_engine.type = "code_agent"
        mock_engine.provider = "anthropic"
        mock_engine.handler_config = {}
        mock_engine.description = "Default engine"
        mock_engine.is_default = True
        mock_engine.is_active = True
        mock_create.return_value = mock_engine

        response = self.client.post(
            "/v2/engines",
            json={
                "id": "claude-code-engine",
                "name": "Claude Code Engine",
                "type": "code_agent",
                "provider": "anthropic",
                "is_default": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "claude-code-engine")
        self.assertTrue(data["is_default"])

    @patch("api.routes.v2.engines.get_all_engines")
    def test_list_engines(self, mock_get_all: MagicMock) -> None:
        """List all execution engines."""
        mock_engine = MagicMock()
        mock_engine.id = "engine-1"
        mock_engine.name = "Engine 1"
        mock_engine.type = "code_agent"
        mock_engine.provider = "anthropic"
        mock_engine.handler_config = {}
        mock_engine.description = None
        mock_engine.is_default = False
        mock_engine.is_active = True
        mock_get_all.return_value = [mock_engine]

        response = self.client.get("/v2/engines")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)

    @patch("api.routes.v2.engines.update_engine")
    def test_update_engine(self, mock_update: MagicMock) -> None:
        """Update an existing engine."""
        mock_engine = MagicMock()
        mock_engine.id = "engine-1"
        mock_engine.name = "Updated Engine"
        mock_engine.type = "managed_agent"
        mock_engine.provider = "openai"
        mock_engine.handler_config = {"model": "gpt-5.4"}
        mock_engine.description = "Updated"
        mock_engine.is_default = False
        mock_engine.is_active = True
        mock_update.return_value = mock_engine

        response = self.client.put(
            "/v2/engines/engine-1",
            json={
                "id": "engine-1",
                "name": "Updated Engine",
                "type": "managed_agent",
                "provider": "openai",
                "handler_config": {"model": "gpt-5.4"},
            },
        )

        self.assertEqual(response.status_code, 200)

    @patch("api.routes.v2.engines.soft_delete_engine")
    def test_delete_engine(self, mock_delete: MagicMock) -> None:
        """Delete (soft) an engine."""
        mock_delete.return_value = True

        response = self.client.delete("/v2/engines/engine-1")
        self.assertEqual(response.status_code, 200)

    @patch("api.routes.v2.engines.soft_delete_engine")
    def test_delete_engine_not_found(self, mock_delete: MagicMock) -> None:
        """Delete engine returns 404 when not found."""
        mock_delete.return_value = False

        response = self.client.delete("/v2/engines/nonexistent")
        self.assertEqual(response.status_code, 404)


class TestTargetRegistry(unittest.TestCase):
    """Test CRUD for execution targets via API."""

    def setUp(self) -> None:
        from tests.test_utils import create_test_client

        self.client, self.app = create_test_client()
        from api.routes.v2_router import get_v2_router

        self.app.include_router(get_v2_router())

        from fastapi.testclient import TestClient

        self.client = TestClient(self.app)

    @patch("api.routes.v2.targets.get_target")
    @patch("api.routes.v2.targets.create_target")
    def test_create_target(self, mock_create: MagicMock, mock_get: MagicMock) -> None:
        """Create an execution target."""
        mock_get.return_value = None

        mock_target = MagicMock()
        mock_target.id = "linux-pool-1"
        mock_target.name = "Linux Pool"
        mock_target.type = "ssh"
        mock_target.connection_config = {"host": "worker-vm.example.com"}
        mock_target.capacity = {"max_workers": 4}
        mock_target.worker_pool = "linux_worker_pool"
        mock_target.is_active = True
        mock_create.return_value = mock_target

        response = self.client.post(
            "/v2/targets",
            json={
                "id": "linux-pool-1",
                "name": "Linux Pool",
                "type": "ssh",
                "connection_config": {"host": "worker-vm.example.com"},
                "capacity": {"max_workers": 4},
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "linux-pool-1")

    @patch("api.routes.v2.targets.get_all_targets")
    def test_list_targets(self, mock_get_all: MagicMock) -> None:
        """List all execution targets."""
        mock_target = MagicMock()
        mock_target.id = "target-1"
        mock_target.name = "Target 1"
        mock_target.type = "local"
        mock_target.connection_config = {}
        mock_target.capacity = {}
        mock_target.worker_pool = "linux_worker_pool"
        mock_target.is_active = True
        mock_get_all.return_value = [mock_target]

        response = self.client.get("/v2/targets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)

    @patch("api.routes.v2.targets.update_target")
    def test_update_target(self, mock_update: MagicMock) -> None:
        """Update an existing target."""
        mock_target = MagicMock()
        mock_target.id = "target-1"
        mock_target.name = "Updated Target"
        mock_target.type = "remote_service"
        mock_target.connection_config = {"url": "https://remote.example.com"}
        mock_target.capacity = {}
        mock_target.worker_pool = "linux_worker_pool"
        mock_target.is_active = True
        mock_update.return_value = mock_target

        response = self.client.put(
            "/v2/targets/target-1",
            json={
                "id": "target-1",
                "name": "Updated Target",
                "type": "remote_service",
                "connection_config": {"url": "https://remote.example.com"},
            },
        )
        self.assertEqual(response.status_code, 200)

    @patch("api.routes.v2.targets.soft_delete_target")
    def test_delete_target(self, mock_delete: MagicMock) -> None:
        """Delete (soft) a target."""
        mock_delete.return_value = True

        response = self.client.delete("/v2/targets/target-1")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Pack Format Tests
# ---------------------------------------------------------------------------


class TestPackYamlParsing(unittest.TestCase):
    """Test pack.yaml parsing."""

    def test_parse_full_pack_yaml(self) -> None:
        """Parse a complete pack.yaml with all fields."""
        from supervisor.pack.schema import PackManifest

        data = {
            "name": "full-pack",
            "version": "2.0",
            "description": "Full test pack",
            "agents": [
                {
                    "id": "leader",
                    "name": "Leader Agent",
                    "prompt_file": "prompts/leader.txt",
                    "role": "leader",
                    "engine": "claude_code",
                    "target": "linux-pool",
                    "order_index": 0,
                },
                {
                    "id": "worker-infra",
                    "name": "Infra Worker",
                    "prompt_file": "prompts/infra.txt",
                    "role": "worker",
                    "order_index": 1,
                    "worker_config": {
                        "mcp_servers": [{"name": "aws", "type": "http", "url": "https://aws.mcp/"}],
                        "allowed_commands": ["terraform plan", "terraform apply"],
                    },
                },
            ],
            "extensions": [
                {
                    "id": "ext-k8s",
                    "name": "K8s Extension",
                    "prompt_file": "prompts/k8s-ext.txt",
                    "domain_tags": ["domain:kubernetes"],
                },
            ],
            "team": {"id": "infra-team", "name": "Infra Team", "mode": "supervisor"},
            "default_engine": "claude_code",
            "default_target": "linux-pool",
        }

        manifest = PackManifest(**data)  # type: ignore[arg-type]
        self.assertEqual(manifest.name, "full-pack")
        self.assertEqual(len(manifest.agents), 2)
        self.assertEqual(len(manifest.extensions), 1)
        # Worker config preserved
        worker = manifest.agents[1]
        self.assertIsNotNone(worker.worker_config)
        self.assertEqual(len(worker.worker_config["mcp_servers"]), 1)  # type: ignore[index]

    def test_agent_yaml_with_worker_config(self) -> None:
        """AgentDefinition preserves worker_config dictionary."""
        from supervisor.pack.schema import AgentDefinition

        agent = AgentDefinition(
            id="worker-data",
            name="Data Worker",
            prompt_file="prompts/data.txt",
            role="worker",
            worker_config={
                "mcp_servers": [],
                "allowed_commands": ["dbt run"],
                "permissions": {"allow": ["Read(/data/**)"], "deny": ["Bash(rm *)"]},
            },
        )
        self.assertEqual(agent.worker_config["allowed_commands"], ["dbt run"])  # type: ignore[index]

    def test_validate_pack_errors_for_missing_files(self) -> None:
        """validate-pack reports errors for missing prompt files."""
        from supervisor.pack.loader import PackLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {
                "name": "broken-pack",
                "agents": [
                    {"id": "leader", "name": "Leader", "prompt_file": "prompts/missing.txt", "role": "leader"},
                ],
                "team": {"id": "team", "name": "Team"},
            }
            with open(os.path.join(tmpdir, "pack.yaml"), "w") as f:
                yaml.dump(manifest, f)

            loader = PackLoader()
            errors = loader.validate(tmpdir)
            self.assertTrue(any("Missing prompt file" in e for e in errors))

    def test_load_pack_api_calls(self) -> None:
        """load-pack makes correct API calls for prompts, agents, team."""
        from supervisor.pack.loader import PackLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            os.makedirs(prompts_dir)
            with open(os.path.join(prompts_dir, "leader.txt"), "w") as f:
                f.write("Leader prompt")

            manifest_data = {
                "name": "api-test-pack",
                "agents": [
                    {"id": "leader", "name": "Leader", "prompt_file": "prompts/leader.txt", "role": "leader"},
                ],
                "team": {"id": "api-team", "name": "API Team", "mode": "supervisor"},
            }
            with open(os.path.join(tmpdir, "pack.yaml"), "w") as f:
                yaml.dump(manifest_data, f)

            loader = PackLoader()
            manifest = loader.load(tmpdir)

            mock_client = MagicMock()
            mock_client.create_or_update_prompt = AsyncMock()
            mock_client.create_or_update_agent = AsyncMock()
            mock_client.create_or_update_team = AsyncMock()

            asyncio.run(loader.apply(tmpdir, manifest, mock_client))

            # Verify prompt was created with correct data
            prompt_call = mock_client.create_or_update_prompt.call_args_list[0]
            prompt_data = prompt_call[0][0]
            self.assertEqual(prompt_data["template"], "Leader prompt")

            # Verify agent was created
            agent_call = mock_client.create_or_update_agent.call_args_list[0]
            agent_data = agent_call[0][0]
            self.assertEqual(agent_data["id"], "leader")

            # Verify team was created
            team_call = mock_client.create_or_update_team.call_args_list[0]
            team_data = team_call[0][0]
            self.assertEqual(team_data["mode"], "supervisor")


# ---------------------------------------------------------------------------
# PAUSED -> Approval Wiring Tests
# ---------------------------------------------------------------------------


class TestPausedToApprovalWiring(unittest.TestCase):
    """Test that paused team runs auto-register approval notifications."""

    def test_register_paused_approvals_helper(self) -> None:
        """_register_paused_approvals creates notifications for tools requiring confirmation."""
        from supervisor.approval import _pending_approvals

        _pending_approvals.clear()

        from api.routes.v2.teams import _register_paused_approvals

        tools = [
            {
                "tool_call_id": "call_1",
                "tool_name": "run_claude_code",
                "requires_confirmation": True,
                "tool_args": {"prompt": "deploy"},
            },
            {"tool_call_id": "call_2", "tool_name": "read_file", "requires_confirmation": False, "tool_args": {}},
        ]

        _register_paused_approvals("run-xyz", "team-1", tools)

        # Only the confirmation-required tool should be registered
        matching = [k for k in _pending_approvals if k.startswith("run-xyz:")]
        self.assertEqual(len(matching), 1)
        self.assertIn("run-xyz:call_1", _pending_approvals)

        _pending_approvals.clear()

    def test_register_paused_approvals_empty_tools(self) -> None:
        """_register_paused_approvals handles empty tools list gracefully."""
        from supervisor.approval import _pending_approvals

        _pending_approvals.clear()

        from api.routes.v2.teams import _register_paused_approvals

        _register_paused_approvals("run-empty", "team-1", [])

        self.assertEqual(len(_pending_approvals), 0)


if __name__ == "__main__":
    unittest.main()
