import json
import logging
from typing import Any, Dict, Optional

from agno.tools import Toolkit

from supervisor.models import ExecutionResult, WorkerConfig
from toolkits.agent_providers.base import AgentProvider

logger = logging.getLogger(__name__)


# Provider registry — maps provider name to class
_PROVIDER_CLASSES: Dict[str, str] = {
    "anthropic": "toolkits.agent_providers.anthropic.AnthropicProvider",
    "openai": "toolkits.agent_providers.openai.OpenAIProvider",
    "google": "toolkits.agent_providers.google.GoogleProvider",
    "webhook": "toolkits.agent_providers.webhook.WebhookProvider",
}


def _load_provider(provider_name: str, handler_config: Optional[Dict[str, Any]] = None) -> AgentProvider:
    """Dynamically load a provider class by name."""
    import importlib

    class_path = _PROVIDER_CLASSES.get(provider_name)
    if not class_path:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(_PROVIDER_CLASSES.keys())}")

    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    provider_class = getattr(module, class_name)

    config = handler_config or {}
    return provider_class(**config)


class ManagedAgentsToolkit(Toolkit):
    """Toolkit that dispatches work to managed agent APIs (Anthropic, OpenAI, Google, custom)."""

    def __init__(
        self,
        user_id: str,
        worker_config: Optional[WorkerConfig] = None,
        provider_name: str = "anthropic",
        handler_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name="managed_agents")
        self.user_id = user_id
        self.worker_config = worker_config or WorkerConfig()
        self.provider_name = provider_name
        self.handler_config = handler_config
        self._provider: Optional[AgentProvider] = None
        self.requires_confirmation_tools = ["run_managed_agent"]
        self.register(self.run_managed_agent)

    @property
    def provider(self) -> AgentProvider:
        if self._provider is None:
            self._provider = _load_provider(self.provider_name, self.handler_config)
        return self._provider

    def run_managed_agent(
        self,
        prompt: str,
        model: str = "claude-sonnet-4-6",
        max_turns: int = 10,
    ) -> str:
        """Execute work via a managed agent API (Anthropic, OpenAI, Google, or custom webhook).

        Args:
            prompt: The task prompt for the managed agent
            model: Model to use for the agent
            max_turns: Maximum number of agent turns

        Returns:
            JSON string with execution result
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, self._run_async(prompt, model, max_turns)).result()
            else:
                result = asyncio.run(self._run_async(prompt, model, max_turns))
        except Exception as e:
            result = ExecutionResult(status="failed", error=str(e))

        return json.dumps(result.model_dump())

    async def _run_async(self, prompt: str, model: str, max_turns: int) -> ExecutionResult:
        """Async execution via the managed agent provider."""
        try:
            # Build MCP server configs from worker_config
            mcp_servers = None
            if self.worker_config.mcp_servers:
                mcp_servers = [
                    {
                        "type": "url" if s.type in ("http", "sse") else "stdio",
                        "name": s.name,
                        **({"url": s.url} if s.url else {}),
                        **({"command": s.command} if s.command else {}),
                    }
                    for s in self.worker_config.mcp_servers
                ]

            agent_id = await self.provider.create_agent(
                prompt=prompt,
                model=model,
                mcp_servers=mcp_servers,
            )

            session_id = await self.provider.create_session(agent_id)
            result = await self.provider.run(session_id, prompt)
            await self.provider.cleanup(agent_id=agent_id, session_id=session_id)
            return result

        except Exception as e:
            logger.error(f"Managed agent execution error: {e}")
            return ExecutionResult(status="failed", error=str(e))
