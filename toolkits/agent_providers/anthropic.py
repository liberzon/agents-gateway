import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from supervisor.models import ExecutionResult
from toolkits.agent_providers.base import AgentProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(AgentProvider):
    """Anthropic managed agents API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self._api_key) if self._api_key else Anthropic()
            except ImportError:
                raise RuntimeError("anthropic package required for AnthropicProvider")
        return self._client

    async def create_agent(
        self,
        prompt: str,
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        client = self._get_client()
        kwargs: Dict[str, Any] = {"name": "worker-agent", "model": model, "instructions": prompt}
        if mcp_servers:
            kwargs["mcp_servers"] = mcp_servers
        if tools:
            kwargs["tools"] = tools
        agent = client.beta.agents.create(**kwargs)
        logger.info(f"Created Anthropic agent: {agent.id}")
        return agent.id

    async def create_session(self, agent_id: str) -> str:
        client = self._get_client()
        session = client.beta.sessions.create(agent=agent_id)
        logger.info(f"Created Anthropic session: {session.id}")
        return session.id

    async def run(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
    ) -> ExecutionResult:
        client = self._get_client()
        output_parts: List[str] = []

        try:
            with client.beta.sessions.stream(session_id) as event_stream:
                # Send the message
                client.beta.sessions.events.send(session_id, events=[{"type": "user.message", "content": message}])
                for event in event_stream:
                    if hasattr(event, "content"):
                        for block in event.content if isinstance(event.content, list) else [event.content]:
                            if hasattr(block, "text"):
                                output_parts.append(block.text)
        except Exception as e:
            logger.error(f"Error running Anthropic session {session_id}: {e}")
            return ExecutionResult(status="failed", error=str(e))

        return ExecutionResult(output="\n".join(output_parts), status="completed")

    async def run_stream(
        self,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        client = self._get_client()
        try:
            client.beta.sessions.events.send(session_id, events=[{"type": "user.message", "content": message}])
            with client.beta.sessions.stream(session_id) as event_stream:
                for event in event_stream:
                    yield {"type": getattr(event, "type", "unknown"), "data": str(event)}
        except Exception as e:
            yield {"type": "error", "data": str(e)}

    async def handle_tool_confirmation(
        self,
        session_id: str,
        tool_use_id: str,
        approved: bool,
        deny_message: Optional[str] = None,
    ) -> None:
        client = self._get_client()
        event: Dict[str, Any] = {
            "type": "user.tool_confirmation",
            "tool_use_id": tool_use_id,
            "result": "allow" if approved else "deny",
        }
        if not approved and deny_message:
            event["deny_message"] = deny_message
        client.beta.sessions.events.send(session_id, events=[event])
