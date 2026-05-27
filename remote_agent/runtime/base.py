from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Optional

from supervisor.models import ExecutionResult


class ContainerRuntime(ABC):
    """Abstract base for container runtimes (Docker, Kubernetes)."""

    @abstractmethod
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
        """Create and start a container. Returns container/pod ID."""

    @abstractmethod
    async def stream_output(self, container_id: str) -> AsyncGenerator[str, None]:
        """Stream stdout from a running container."""

    @abstractmethod
    async def collect_result(self, container_id: str) -> ExecutionResult:
        """Wait for container to finish and collect the result."""

    @abstractmethod
    async def destroy_container(self, container_id: str) -> None:
        """Stop and remove a container."""

    @abstractmethod
    async def get_exit_code(self, container_id: str) -> Optional[int]:
        """Get the exit code of a completed container."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the runtime is available and healthy."""

    async def get_oom_status(self, container_id: str) -> bool:
        """Check if a container was OOM-killed. Override per runtime."""
        exit_code = await self.get_exit_code(container_id)
        return exit_code == 137
