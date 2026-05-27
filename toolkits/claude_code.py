import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional

from agno.tools import Toolkit

from supervisor.models import ExecutionResult, WorkerConfig
from supervisor.plugins.generator import PluginConfigGenerator

logger = logging.getLogger(__name__)


class ClaudeCodeToolkit(Toolkit):
    """Toolkit that dispatches work to Claude Code CLI with MCP plugins and control hooks."""

    def __init__(
        self,
        user_id: str,
        worker_config: Optional[WorkerConfig] = None,
        execution_target_type: str = "local",
        remote_host: Optional[str] = None,
        remote_api_url: Optional[str] = None,
    ):
        super().__init__(name="claude_code")
        self.user_id = user_id
        self.worker_config = worker_config or WorkerConfig()
        self.execution_target_type = execution_target_type
        self.remote_host = remote_host
        self.remote_api_url = remote_api_url
        self._plugin_generator = PluginConfigGenerator()
        self.requires_confirmation_tools = ["run_claude_code"]
        self.register(self.run_claude_code)
        self.register(self.run_claude_code_streaming)

    def run_claude_code(
        self,
        prompt: str,
        repo_path: str = ".",
        model: str = "claude-sonnet-4-6",
        max_turns: int = 10,
        timeout_minutes: int = 15,
    ) -> str:
        """Execute work via Claude Code CLI with configured MCP plugins and control hooks.

        Args:
            prompt: The task prompt for Claude Code to execute
            repo_path: Path to the repository to work in
            model: Claude model to use
            max_turns: Maximum number of agent turns
            timeout_minutes: Timeout in minutes

        Returns:
            JSON string with execution result
        """
        if self.execution_target_type == "local":
            result = self._run_local(prompt, repo_path, model, max_turns, timeout_minutes)
        elif self.execution_target_type == "ssh":
            result = self._run_ssh(prompt, repo_path, model, max_turns, timeout_minutes)
        elif self.execution_target_type == "remote_service":
            result = self._run_remote_service(prompt, repo_path, model, max_turns, timeout_minutes)
        else:
            result = ExecutionResult(status="failed", error=f"Unknown target type: {self.execution_target_type}")

        return json.dumps(result.model_dump())

    def run_claude_code_streaming(
        self,
        prompt: str,
        repo_path: str = ".",
        model: str = "claude-sonnet-4-6",
        max_turns: int = 10,
        timeout_minutes: int = 15,
    ) -> str:
        """Execute work via Claude Code CLI with streaming output and permission tracking.

        Returns all events including tool calls, permission denials, and the final result.
        Use this when you need visibility into what Claude Code is doing.

        Args:
            prompt: The task prompt for Claude Code
            repo_path: Path to the repository
            model: Claude model to use
            max_turns: Maximum agent turns
            timeout_minutes: Timeout in minutes

        Returns:
            JSON string with execution result including permission_denials
        """
        collected_events: List[Dict[str, Any]] = []

        def on_event(event: Dict[str, Any]) -> None:
            event_type = event.get("type", "")
            # Only collect meaningful events, skip verbose system noise
            if event_type in ("assistant", "user", "result", "tool_use", "tool_result"):
                collected_events.append({"type": event_type, "summary": str(event)[:200]})

        result = self._run_local_streaming(prompt, repo_path, model, max_turns, timeout_minutes, on_event=on_event)
        result.commands_run = [f"events_captured: {len(collected_events)}"]
        return json.dumps(result.model_dump())

    def _run_local(
        self, prompt: str, repo_path: str, model: str, max_turns: int, timeout_minutes: int
    ) -> ExecutionResult:
        """Run Claude Code CLI as a local subprocess."""
        workspace_dir = tempfile.mkdtemp(prefix="claude_code_")
        try:
            self._plugin_generator.write_workspace_config(workspace_dir, self.worker_config)

            cmd = self._build_cli_command(prompt, model, max_turns, workspace_dir)

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout_minutes * 60,
            )

            return self._parse_cli_output(result.stdout, result.stderr, result.returncode)

        except subprocess.TimeoutExpired:
            return ExecutionResult(status="failed", error=f"Timed out after {timeout_minutes} minutes")
        except FileNotFoundError:
            return ExecutionResult(status="failed", error="claude CLI not found on PATH")
        except Exception as e:
            return ExecutionResult(status="failed", error=str(e))
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _run_ssh(
        self, prompt: str, repo_path: str, model: str, max_turns: int, timeout_minutes: int
    ) -> ExecutionResult:
        """Run Claude Code CLI via SSH on a remote host."""
        if not self.remote_host:
            return ExecutionResult(status="failed", error="No remote_host configured for SSH dispatch")

        escaped_prompt = prompt.replace("'", "'\\''")
        ssh_cmd = [
            "ssh",
            self.remote_host,
            f"cd {repo_path} && claude --print --output-format json "
            f"--model {model} --max-turns {max_turns} "
            f"'{escaped_prompt}'",
        ]

        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout_minutes * 60)
            return self._parse_cli_output(result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            return ExecutionResult(status="failed", error=f"SSH execution timed out after {timeout_minutes}m")
        except Exception as e:
            return ExecutionResult(status="failed", error=f"SSH error: {e}")

    def _run_remote_service(
        self, prompt: str, repo_path: str, model: str, max_turns: int, timeout_minutes: int
    ) -> ExecutionResult:
        """Submit to remote agent service via HTTP."""
        if not self.remote_api_url:
            return ExecutionResult(status="failed", error="No remote_api_url configured")

        try:
            import httpx

            response = httpx.post(
                f"{self.remote_api_url}/execute",
                json={
                    "prompt": prompt,
                    "repo_path": repo_path,
                    "model": model,
                    "max_turns": max_turns,
                    "timeout_minutes": timeout_minutes,
                    "worker_config": self.worker_config.model_dump(),
                },
                timeout=timeout_minutes * 60 + 30,
            )
            response.raise_for_status()
            return ExecutionResult(**response.json())
        except Exception as e:
            return ExecutionResult(status="failed", error=f"Remote service error: {e}")

    def _build_cli_command(
        self,
        prompt: str,
        model: str,
        max_turns: int,
        workspace_dir: str,
        stream: bool = False,
    ) -> List[str]:
        cmd = [
            "claude",
            "--print",
            "--output-format",
            "stream-json" if stream else "json",
            "--model",
            model,
            "--max-turns",
            str(max_turns),
        ]

        if stream:
            cmd.append("--verbose")

        # Add MCP config if it exists
        mcp_path = os.path.join(workspace_dir, ".mcp.json")
        if os.path.exists(mcp_path):
            cmd.extend(["--mcp-config", mcp_path])

        # Add settings if they exist (permissions + hooks)
        settings_path = os.path.join(workspace_dir, ".claude", "settings.json")
        if os.path.exists(settings_path):
            cmd.extend(["--settings", settings_path])

        cmd.extend(["-p", prompt])
        return cmd

    def _run_local_streaming(
        self,
        prompt: str,
        repo_path: str,
        model: str,
        max_turns: int,
        timeout_minutes: int,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> ExecutionResult:
        """Run Claude Code CLI with stream-json output, capturing all events.

        Events include tool calls, permission denials, thinking, and results.
        The on_event callback receives each parsed JSON event.
        """
        workspace_dir = tempfile.mkdtemp(prefix="claude_code_stream_")
        try:
            self._plugin_generator.write_workspace_config(workspace_dir, self.worker_config)
            cmd = self._build_cli_command(prompt, model, max_turns, workspace_dir, stream=True)

            proc = subprocess.Popen(
                cmd,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            events: List[Dict[str, Any]] = []
            result_event: Optional[Dict[str, Any]] = None
            permission_denials: List[Dict[str, Any]] = []

            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)

                    event_type = event.get("type", "")

                    # Capture permission denials
                    if event_type == "result":
                        result_event = event
                        denials = event.get("permission_denials", [])
                        permission_denials.extend(denials)

                    # Forward events to callback
                    if on_event:
                        on_event(event)

                except json.JSONDecodeError:
                    continue

            proc.wait(timeout=timeout_minutes * 60)
            stderr_output = proc.stderr.read() if proc.stderr else ""

            # Build result from collected events
            if result_event:
                return ExecutionResult(
                    output=result_event.get("result", ""),
                    status="completed" if not result_event.get("is_error") else "failed",
                    error=result_event.get("error") if result_event.get("is_error") else None,
                    verification_results={
                        "permission_denials": permission_denials,
                        "num_turns": result_event.get("num_turns", 0),
                        "duration_ms": result_event.get("duration_ms", 0),
                        "total_cost_usd": result_event.get("total_cost_usd", 0),
                        "terminal_reason": result_event.get("terminal_reason", ""),
                    },
                    duration_seconds=result_event.get("duration_ms", 0) / 1000.0,
                )

            return self._parse_cli_output("", stderr_output, proc.returncode or 0)

        except subprocess.TimeoutExpired:
            proc.terminate()
            return ExecutionResult(status="failed", error=f"Timed out after {timeout_minutes} minutes")
        except FileNotFoundError:
            return ExecutionResult(status="failed", error="claude CLI not found on PATH")
        except Exception as e:
            return ExecutionResult(status="failed", error=str(e))
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _parse_cli_output(self, stdout: str, stderr: str, returncode: int) -> ExecutionResult:
        if returncode == 137:
            return ExecutionResult(status="oom", error="Process killed (OOM)")

        try:
            data = json.loads(stdout) if stdout.strip() else {}
            return ExecutionResult(
                output=data.get("result", stdout),
                files_changed=data.get("files_changed", []),
                commands_run=data.get("commands_run", []),
                status="completed" if returncode == 0 else "failed",
                error=stderr if returncode != 0 else None,
            )
        except json.JSONDecodeError:
            return ExecutionResult(
                output=stdout,
                status="completed" if returncode == 0 else "failed",
                error=stderr if returncode != 0 else None,
            )
