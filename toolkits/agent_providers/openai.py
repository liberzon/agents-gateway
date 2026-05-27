import logging
from typing import Any, Dict, List, Optional

from supervisor.models import ExecutionResult
from toolkits.agent_providers.base import AgentProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AgentProvider):
    """OpenAI Agents API provider (Responses API with tools)."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self._api_key) if self._api_key else OpenAI()
            except ImportError:
                raise RuntimeError("openai package required for OpenAIProvider")
        return self._client

    async def create_agent(
        self,
        prompt: str,
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        client = self._get_client()
        kwargs: Dict[str, Any] = {"model": model, "instructions": prompt}
        if tools:
            kwargs["tools"] = tools
        assistant = client.beta.assistants.create(**kwargs)
        logger.info(f"Created OpenAI assistant: {assistant.id}")
        return assistant.id

    async def create_session(self, agent_id: str) -> str:
        client = self._get_client()
        thread = client.beta.threads.create()
        logger.info(f"Created OpenAI thread: {thread.id}")
        return f"{agent_id}:{thread.id}"

    async def run(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
    ) -> ExecutionResult:
        client = self._get_client()
        agent_id, thread_id = session_id.split(":", 1)
        try:
            client.beta.threads.messages.create(thread_id=thread_id, role="user", content=message)
            client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=agent_id)
            messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
            output = ""
            for msg in messages.data:
                for block in msg.content:
                    if hasattr(block, "text"):
                        output += block.text.value
            return ExecutionResult(output=output, status="completed")
        except Exception as e:
            logger.error(f"Error running OpenAI session: {e}")
            return ExecutionResult(status="failed", error=str(e))

    async def handle_tool_confirmation(
        self,
        session_id: str,
        tool_use_id: str,
        approved: bool,
        deny_message: Optional[str] = None,
    ) -> None:
        # OpenAI uses submit_tool_outputs for tool confirmation
        logger.info(f"OpenAI tool confirmation for {tool_use_id}: {'approved' if approved else 'denied'}")
