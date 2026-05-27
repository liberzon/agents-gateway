"""Tests for supervisor Pydantic models."""

import unittest

from supervisor.models import (
    Classification,
    ExecutionLimits,
    ExecutionResult,
    JobSpec,
    JobStatus,
    MCPServerConfig,
    PermissionRules,
    RetryPolicy,
    RiskLevel,
    StreamVerbosity,
    SupervisorResponse,
    WorkerConfig,
    WorkerType,
)


class TestEnums(unittest.TestCase):
    def test_stream_verbosity(self) -> None:
        assert StreamVerbosity.full == "full"
        assert StreamVerbosity.events == "events"
        assert StreamVerbosity.result == "result"

    def test_job_status(self) -> None:
        assert JobStatus.queued == "queued"
        assert JobStatus.oom == "oom"
        assert JobStatus.failed_circuit_open == "failed_circuit_open"

    def test_worker_types(self) -> None:
        assert WorkerType.coding == "coding"
        assert WorkerType.operations == "operations"
        assert WorkerType.data_platform == "data_platform"

    def test_classification(self) -> None:
        assert Classification.code_fix == "code_fix"
        assert Classification.high_risk_escalation == "high_risk_escalation"


class TestMCPServerConfig(unittest.TestCase):
    def test_stdio_server(self) -> None:
        config = MCPServerConfig(name="git", type="stdio", command="npx", args=["-y", "@anthropic/mcp-git"])
        assert config.name == "git"
        assert config.type == "stdio"
        assert config.command == "npx"

    def test_http_server(self) -> None:
        config = MCPServerConfig(name="github", type="http", url="https://api.github.com/mcp")
        assert config.url == "https://api.github.com/mcp"

    def test_defaults(self) -> None:
        config = MCPServerConfig(name="test")
        assert config.type == "stdio"
        assert config.args == []
        assert config.env == {}


class TestWorkerConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        config = WorkerConfig()
        assert config.mcp_servers == []
        assert config.worker_pool == "linux_worker_pool"
        assert config.permissions.allow == []

    def test_full_config(self) -> None:
        config = WorkerConfig(
            mcp_servers=[MCPServerConfig(name="git", command="npx")],
            permissions=PermissionRules(allow=["Read(**)"]),
            execution_engine_preference="claude_code",
            allowed_tools=["bash", "git"],
        )
        assert len(config.mcp_servers) == 1
        assert config.execution_engine_preference == "claude_code"
        assert "bash" in config.allowed_tools


class TestExecutionLimits(unittest.TestCase):
    def test_defaults(self) -> None:
        limits = ExecutionLimits()
        assert limits.network_access is False
        assert limits.allow_git_push is False
        assert limits.max_runtime_minutes == 15
        assert limits.max_memory_mb == 4096

    def test_custom_limits(self) -> None:
        limits = ExecutionLimits(network_access=True, max_memory_mb=8192, max_cpus=4.0)
        assert limits.network_access is True
        assert limits.max_memory_mb == 8192


class TestJobSpec(unittest.TestCase):
    def test_defaults(self) -> None:
        spec = JobSpec()
        assert spec.job_type == "none"
        assert spec.environment == "unknown"
        assert len(spec.output_contract) == 5

    def test_full_spec(self) -> None:
        spec = JobSpec(
            job_type="coding",
            objective="Fix the login bug",
            repository="myrepo",
            allowed_directories=["/src"],
            forbidden_actions=["rm -rf", "git push --force"],
        )
        assert spec.job_type == "coding"
        assert len(spec.forbidden_actions) == 2


class TestSupervisorResponse(unittest.TestCase):
    def test_defaults(self) -> None:
        resp = SupervisorResponse()
        assert resp.should_invoke_worker is False
        assert resp.risk_level == RiskLevel.low

    def test_with_job(self) -> None:
        resp = SupervisorResponse(
            classification=Classification.code_fix,
            should_invoke_worker=True,
            worker_type="coding",
            execution_engine="claude_code",
            risk_level=RiskLevel.medium,
            job=JobSpec(objective="Fix bug"),
        )
        assert resp.should_invoke_worker is True
        assert resp.job.objective == "Fix bug"


class TestExecutionResult(unittest.TestCase):
    def test_defaults(self) -> None:
        result = ExecutionResult()
        assert result.status == "completed"
        assert result.retry_count == 0

    def test_failure(self) -> None:
        result = ExecutionResult(status="oom", error="Container OOM-killed")
        assert result.status == "oom"


class TestRetryPolicy(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_retries == 2
        assert policy.memory_multiplier == 2.0
        assert policy.circuit_breaker_threshold == 3


class TestAgentConfigBackwardCompat(unittest.TestCase):
    def test_worker_config_optional(self) -> None:
        from db.agent_info_crud import AgentConfig

        config = AgentConfig()
        assert config.worker_config is None
        assert config.enable_memory is True

    def test_with_worker_config(self) -> None:
        from db.agent_info_crud import AgentConfig

        config = AgentConfig(worker_config=WorkerConfig(worker_pool="mac_worker_pool"))
        assert config.worker_config is not None
        assert config.worker_config.worker_pool == "mac_worker_pool"


if __name__ == "__main__":
    unittest.main()
