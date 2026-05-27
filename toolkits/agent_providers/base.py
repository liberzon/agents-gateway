from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

from supervisor.models import ExecutionResult


class AgentProvider(ABC):
    """Abstract base for managed agent providers (Anthropic, OpenAI, Google, custom)."""

    @abstractmethod
    async def create_agent(
        self,
        prompt: str,
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Create an agent and return its ID."""

    @abstractmethod
    async def create_session(self, agent_id: str) -> str:
        """Create a session for an agent and return the session ID."""

    @abstractmethod
    async def run(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
    ) -> ExecutionResult:
        """Run a message in a session and return the result."""

    async def run_stream(
        self,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream events from a session run. Override for streaming support."""
        result = await self.run(session_id, message, stream=False)
        yield {"type": "message", "content": result.output}

    @abstractmethod
    async def handle_tool_confirmation(
        self,
        session_id: str,
        tool_use_id: str,
        approved: bool,
        deny_message: Optional[str] = None,
    ) -> None:
        """Approve or deny a tool call in a session."""

    async def cleanup(self, agent_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Clean up agent/session resources. Override if needed."""
