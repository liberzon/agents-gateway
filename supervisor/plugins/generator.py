import json
import logging
import os
import stat
from typing import Any, Dict, Optional

from supervisor.models import JobSpec, MCPServerConfig, WorkerConfig

logger = logging.getLogger(__name__)


class PluginConfigGenerator:
    """Generates Claude Code plugin configs (.mcp.json, settings.json, hooks) from WorkerConfig + JobSpec."""

    def generate_mcp_json(self, worker_config: WorkerConfig, job_spec: Optional[JobSpec] = None) -> Dict[str, Any]:
        """Generate .mcp.json content from worker's MCP server configs."""
        mcp_servers: Dict[str, Any] = {}
        for server in worker_config.mcp_servers:
            entry = self._mcp_server_to_dict(server)
            mcp_servers[server.name] = entry
        return {"mcpServers": mcp_servers}

    def _mcp_server_to_dict(self, server: MCPServerConfig) -> Dict[str, Any]:
        if server.type in ("http", "sse"):
            entry: Dict[str, Any] = {"type": server.type}
            if server.url:
                entry["url"] = server.url
            if server.headers:
                entry["headers"] = server.headers
        else:  # stdio
            entry = {}
            if server.command:
                entry["command"] = server.command
            if server.args:
                entry["args"] = server.args
            if server.env:
                entry["env"] = server.env
        return entry

    def generate_settings_json(self, worker_config: WorkerConfig, job_spec: Optional[JobSpec] = None) -> Dict[str, Any]:
        """Generate settings.json with hooks and permissions from worker config + job spec constraints."""
        permissions = self._build_permissions(worker_config, job_spec)
        hooks = self._build_hooks(worker_config, job_spec)

        settings: Dict[str, Any] = {"permissions": permissions}
        if hooks:
            settings["hooks"] = hooks
        return settings

    def _build_permissions(self, worker_config: WorkerConfig, job_spec: Optional[JobSpec] = None) -> Dict[str, Any]:
        rules = worker_config.permissions
        allow = list(rules.allow)
        deny = list(rules.deny)
        ask = list(rules.ask)

        if job_spec:
            # Convert job spec constraints into permission rules
            for directory in job_spec.allowed_directories:
                allow.append(f"Read({directory}/**)")
                allow.append(f"Edit({directory}/**)")
            for directory in job_spec.forbidden_directories:
                deny.append(f"Read({directory}/**)")
                deny.append(f"Edit({directory}/**)")
            for cmd in job_spec.allowed_commands:
                allow.append(f"Bash({cmd} *)")
            for action in job_spec.forbidden_actions:
                deny.append(f"Bash({action})")

            # Enforce execution limits as denials
            limits = job_spec.execution_limits
            if not limits.allow_git_push:
                deny.append("Bash(git push *)")
            if not limits.allow_delete_files:
                deny.append("Bash(rm -rf *)")
                deny.append("Bash(rm -r *)")
            if not limits.allow_migrations:
                deny.append("Bash(*migrate*)")

        return {"allow": allow, "deny": deny, "ask": ask}

    def _build_hooks(self, worker_config: WorkerConfig, job_spec: Optional[JobSpec] = None) -> Dict[str, Any]:
        hooks: Dict[str, list] = {}
        for hook_config in worker_config.hooks:
            event = hook_config.event
            if event not in hooks:
                hooks[event] = []
            hook_entry: Dict[str, Any] = {
                "matcher": hook_config.matcher,
                "hooks": [
                    {
                        "type": hook_config.hook_type,
                        hook_config.hook_type: hook_config.command_or_url,
                        "timeout": hook_config.timeout,
                    }
                ],
            }
            hooks[event].append(hook_entry)
        return hooks

    def generate_enforcement_hook(self, job_spec: JobSpec) -> str:
        """Generate a shell script for PreToolUse hook that enforces job constraints."""
        forbidden = json.dumps(job_spec.forbidden_actions)
        allowed_dirs = json.dumps(job_spec.allowed_directories)

        return f"""#!/bin/bash
# Auto-generated enforcement hook for PreToolUse
# Checks tool calls against job spec constraints

TOOL_INPUT=$(cat /dev/stdin)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$TOOL_INPUT" | jq -r '.tool_input.command // empty')
FILE_PATH=$(echo "$TOOL_INPUT" | jq -r '.tool_input.file_path // empty')

FORBIDDEN_ACTIONS='{forbidden}'
ALLOWED_DIRS='{allowed_dirs}'

# Check forbidden actions
if [ -n "$COMMAND" ]; then
    for action in $(echo "$FORBIDDEN_ACTIONS" | jq -r '.[]'); do
        if echo "$COMMAND" | grep -qF "$action"; then
            echo '{{"hookSpecificOutput": {{"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Forbidden action: '$action'"}}}}'
            exit 0
        fi
    done
fi

# Allow by default
exit 0
"""

    def write_workspace_config(
        self,
        workspace_dir: str,
        worker_config: WorkerConfig,
        job_spec: Optional[JobSpec] = None,
    ) -> str:
        """Write .mcp.json + settings.json + hook scripts to workspace directory."""
        claude_dir = os.path.join(workspace_dir, ".claude")
        hooks_dir = os.path.join(claude_dir, "hooks")
        os.makedirs(hooks_dir, exist_ok=True)

        # Write .mcp.json
        mcp_json = self.generate_mcp_json(worker_config, job_spec)
        mcp_path = os.path.join(workspace_dir, ".mcp.json")
        with open(mcp_path, "w") as f:
            json.dump(mcp_json, f, indent=2)

        # Write settings.json
        settings = self.generate_settings_json(worker_config, job_spec)

        # Add enforcement hook if job_spec provided
        if job_spec and job_spec.forbidden_actions:
            hook_script = self.generate_enforcement_hook(job_spec)
            hook_path = os.path.join(hooks_dir, "enforce.sh")
            with open(hook_path, "w") as f:
                f.write(hook_script)
            os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC)

            # Add the enforcement hook to settings
            pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
            pre_tool_use.append(
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": hook_path, "timeout": 10}],
                }
            )
            settings.setdefault("hooks", {})["PreToolUse"] = pre_tool_use

        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Wrote workspace config to {workspace_dir}")
        return workspace_dir
