"""Tests for plugin config generator."""

import json
import os
import tempfile
import unittest

from supervisor.models import (
    ExecutionLimits,
    HookConfig,
    JobSpec,
    MCPServerConfig,
    PermissionRules,
    WorkerConfig,
)
from supervisor.plugins.generator import PluginConfigGenerator


class TestPluginConfigGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = PluginConfigGenerator()
        self.worker_config = WorkerConfig(
            mcp_servers=[
                MCPServerConfig(name="git", type="stdio", command="npx", args=["-y", "@anthropic/mcp-git"]),
                MCPServerConfig(name="github", type="http", url="https://api.github.com/mcp"),
            ],
            permissions=PermissionRules(
                allow=["Read(/src/**)"],
                deny=["Bash(rm -rf *)"],
                ask=["Bash(git push *)"],
            ),
            hooks=[
                HookConfig(event="PreToolUse", matcher="Bash", hook_type="command", command_or_url="/hooks/enforce.sh"),
            ],
        )

    def test_generate_mcp_json_stdio(self) -> None:
        result = self.generator.generate_mcp_json(self.worker_config)
        servers = result["mcpServers"]
        assert "git" in servers
        assert servers["git"]["command"] == "npx"
        assert servers["git"]["args"] == ["-y", "@anthropic/mcp-git"]

    def test_generate_mcp_json_http(self) -> None:
        result = self.generator.generate_mcp_json(self.worker_config)
        servers = result["mcpServers"]
        assert "github" in servers
        assert servers["github"]["type"] == "http"
        assert servers["github"]["url"] == "https://api.github.com/mcp"

    def test_generate_settings_json_permissions(self) -> None:
        result = self.generator.generate_settings_json(self.worker_config)
        perms = result["permissions"]
        assert "Read(/src/**)" in perms["allow"]
        assert "Bash(rm -rf *)" in perms["deny"]
        assert "Bash(git push *)" in perms["ask"]

    def test_generate_settings_json_hooks(self) -> None:
        result = self.generator.generate_settings_json(self.worker_config)
        assert "hooks" in result
        assert "PreToolUse" in result["hooks"]

    def test_job_spec_constraints_added_to_permissions(self) -> None:
        job_spec = JobSpec(
            allowed_directories=["/src", "/tests"],
            forbidden_directories=["/secrets"],
            allowed_commands=["git", "pytest"],
            forbidden_actions=["rm -rf /"],
            execution_limits=ExecutionLimits(allow_git_push=False, allow_delete_files=False),
        )
        result = self.generator.generate_settings_json(self.worker_config, job_spec)
        perms = result["permissions"]

        # Allowed directories added
        assert "Read(/src/**)" in perms["allow"]
        assert "Edit(/src/**)" in perms["allow"]
        assert "Read(/tests/**)" in perms["allow"]

        # Forbidden directories denied
        assert "Read(/secrets/**)" in perms["deny"]

        # Forbidden actions denied
        assert "Bash(rm -rf /)" in perms["deny"]

        # Execution limits enforced
        assert "Bash(git push *)" in perms["deny"]
        assert "Bash(rm -rf *)" in perms["deny"]

    def test_generate_enforcement_hook(self) -> None:
        job_spec = JobSpec(forbidden_actions=["rm -rf /", "DROP TABLE"])
        script = self.generator.generate_enforcement_hook(job_spec)
        assert "#!/bin/bash" in script
        assert "rm -rf /" in script
        assert "DROP TABLE" in script
        assert "permissionDecision" in script

    def test_write_workspace_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.generator.write_workspace_config(tmpdir, self.worker_config)

            # Check .mcp.json exists
            mcp_path = os.path.join(tmpdir, ".mcp.json")
            assert os.path.exists(mcp_path)
            with open(mcp_path) as f:
                mcp_data = json.load(f)
            assert "mcpServers" in mcp_data

            # Check settings.json exists
            settings_path = os.path.join(tmpdir, ".claude", "settings.json")
            assert os.path.exists(settings_path)
            with open(settings_path) as f:
                settings_data = json.load(f)
            assert "permissions" in settings_data

    def test_write_workspace_config_with_enforcement(self) -> None:
        job_spec = JobSpec(forbidden_actions=["dangerous_action"])
        with tempfile.TemporaryDirectory() as tmpdir:
            self.generator.write_workspace_config(tmpdir, self.worker_config, job_spec)

            hook_path = os.path.join(tmpdir, ".claude", "hooks", "enforce.sh")
            assert os.path.exists(hook_path)
            assert os.access(hook_path, os.X_OK)


if __name__ == "__main__":
    unittest.main()
