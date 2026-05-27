import logging
import shutil
import tempfile
from typing import Optional

from supervisor.models import ExecutionResult, JobSpec, WorkerConfig
from supervisor.plugins.generator import PluginConfigGenerator
from remote_agent.runtime.base import ContainerRuntime

logger = logging.getLogger(__name__)

DEFAULT_WORKER_IMAGE = "claude-code-worker:latest"


class ContainerExecutor:
    """Orchestrates container lifecycle: workspace setup → spawn → collect → cleanup."""

    def __init__(self, runtime: ContainerRuntime, worker_image: str = DEFAULT_WORKER_IMAGE):
        self.runtime = runtime
        self.worker_image = worker_image
        self._plugin_generator = PluginConfigGenerator()

    async def execute(
        self,
        prompt: str,
        worker_config: WorkerConfig,
        job_spec: Optional[JobSpec] = None,
        repo_url: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_turns: int = 10,
        timeout_minutes: int = 15,
        memory_limit_mb: Optional[int] = None,
        cpu_limit: Optional[float] = None,
        network_enabled: bool = False,
    ) -> ExecutionResult:
        """Full execution lifecycle."""
        workspace_dir = tempfile.mkdtemp(prefix="worker_")
        container_id = None

        try:
            # 1. Write plugin configs to workspace
            self._plugin_generator.write_workspace_config(workspace_dir, worker_config, job_spec)

            # 2. Clone repo if URL provided
            if repo_url:
                self._clone_repo(repo_url, workspace_dir)

            # 3. Build command
            command = [
                "claude",
                "--print",
                "--output-format",
                "json",
                "--model",
                model,
                "--max-turns",
                str(max_turns),
                prompt,
            ]

            # 4. Determine resource limits
            limits = job_spec.execution_limits if job_spec else None
            effective_memory = memory_limit_mb or (limits.max_memory_mb if limits else 4096)
            effective_cpu = cpu_limit or (limits.max_cpus if limits else 2.0)
            effective_network = network_enabled or (limits.network_access if limits else False)

            # 5. Create and run container
            container_id = await self.runtime.create_container(
                image=self.worker_image,
                workspace_dir=workspace_dir,
                command=command,
                cpu_limit=effective_cpu,
                memory_limit_mb=effective_memory,
                network_enabled=effective_network,
                labels={"supervisor": "true", "worker-type": job_spec.job_type if job_spec else "unknown"},
            )

            # 6. Collect result
            result = await self.runtime.collect_result(container_id)
            result.container_id = container_id

            # 7. Check for OOM
            if await self.runtime.get_oom_status(container_id):
                result.status = "oom"
                result.error = "Container OOM-killed"

            return result

        except Exception as e:
            logger.error(f"Container execution error: {e}")
            return ExecutionResult(
                status="failed",
                error=str(e),
                container_id=container_id,
            )
        finally:
            # Cleanup
            if container_id:
                try:
                    await self.runtime.destroy_container(container_id)
                except Exception as e:
                    logger.warning(f"Error cleaning up container: {e}")
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _clone_repo(self, repo_url: str, workspace_dir: str) -> None:
        import subprocess

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, workspace_dir],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except Exception as e:
            logger.warning(f"Failed to clone {repo_url}: {e}")
