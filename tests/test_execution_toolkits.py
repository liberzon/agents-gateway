"""Tests for execution engine toolkits."""

import json
import unittest
from unittest.mock import MagicMock, patch

from supervisor.models import MCPServerConfig, PermissionRules, WorkerConfig
from toolkits.claude_code import ClaudeCodeToolkit
from toolkits.managed_agents import ManagedAgentsToolkit


class TestClaudeCodeToolkit(unittest.TestCase):
    def setUp(self) -> None:
        self.worker_config = WorkerConfig(
            mcp_servers=[
                MCPServerConfig(name="git", type="stdio", command="npx", args=["-y", "@anthropic/mcp-git"]),
            ],
            permissions=PermissionRules(allow=["Read(**)"]),
        )
        self.toolkit = ClaudeCodeToolkit(user_id="test-user", worker_config=self.worker_config)

    def test_init(self) -> None:
        assert self.toolkit.user_id == "test-user"
        assert self.toolkit.execution_target_type == "local"
        assert "run_claude_code" in self.toolkit.requires_confirmation_tools

    def test_build_cli_command(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a .mcp.json so the command includes it
            import os

            mcp_path = os.path.join(tmpdir, ".mcp.json")
            with open(mcp_path, "w") as f:
                json.dump({"mcpServers": {}}, f)

            cmd = self.toolkit._build_cli_command("fix the bug", "claude-sonnet-4-6", 10, tmpdir)
            assert "claude" in cmd
            assert "--print" in cmd
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "--model" in cmd
            assert "claude-sonnet-4-6" in cmd
            assert "--mcp-config" in cmd

    def test_parse_cli_output_success(self) -> None:
        stdout = json.dumps({"result": "Done", "files_changed": ["a.py"]})
        result = self.toolkit._parse_cli_output(stdout, "", 0)
        assert result.status == "completed"
        assert result.output == "Done"
        assert "a.py" in result.files_changed

    def test_parse_cli_output_failure(self) -> None:
        result = self.toolkit._parse_cli_output("", "Error occurred", 1)
        assert result.status == "failed"
        assert result.error == "Error occurred"

    def test_parse_cli_output_oom(self) -> None:
        result = self.toolkit._parse_cli_output("", "", 137)
        assert result.status == "oom"

    @patch("subprocess.run")
    def test_run_local_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout=json.dumps({"result": "Task completed"}), stderr="", returncode=0)
        result = self.toolkit._run_local("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        assert result.status == "completed"

    def test_run_ssh_no_host(self) -> None:
        result = self.toolkit._run_ssh("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        assert result.status == "failed"
        assert "No remote_host" in (result.error or "")

    def test_run_remote_service_no_url(self) -> None:
        result = self.toolkit._run_remote_service("fix bug", ".", "claude-sonnet-4-6", 10, 15)
        assert result.status == "failed"
        assert "No remote_api_url" in (result.error or "")


class TestManagedAgentsToolkit(unittest.TestCase):
    def setUp(self) -> None:
        self.worker_config = WorkerConfig(
            mcp_servers=[MCPServerConfig(name="github", type="http", url="https://api.github.com/mcp")],
        )
        self.toolkit = ManagedAgentsToolkit(
            user_id="test-user", worker_config=self.worker_config, provider_name="anthropic"
        )

    def test_init(self) -> None:
        assert self.toolkit.user_id == "test-user"
        assert self.toolkit.provider_name == "anthropic"
        assert "run_managed_agent" in self.toolkit.requires_confirmation_tools


if __name__ == "__main__":
    unittest.main()
