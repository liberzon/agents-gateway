import logging
from typing import Any, Dict, List, Optional

import httpx

from supervisor.models import ExecutionResult
from toolkits.agent_providers.base import AgentProvider

logger = logging.getLogger(__name__)


class WebhookProvider(AgentProvider):
    """Custom webhook-based agent provider for extensible integrations."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers = headers or {}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def create_agent(
        self,
        prompt: str,
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/agents",
                json={"prompt": prompt, "model": model, "tools": tools, "mcp_servers": mcp_servers},
                headers=self._headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json().get("agent_id", "unknown")

    async def create_session(self, agent_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sessions",
                json={"agent_id": agent_id},
                headers=self._headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json().get("session_id", "unknown")

    async def run(
        self,
        session_id: str,
        message: str,
        stream: bool = False,
    ) -> ExecutionResult:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/sessions/{session_id}/run",
                    json={"message": message, "stream": stream},
                    headers=self._headers,
                    timeout=900.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return ExecutionResult(
                    output=data.get("output", ""),
                    files_changed=data.get("files_changed", []),
                    commands_run=data.get("commands_run", []),
                    status=data.get("status", "completed"),
                    error=data.get("error"),
                )
            except Exception as e:
                logger.error(f"Webhook provider error: {e}")
                return ExecutionResult(status="failed", error=str(e))

    async def handle_tool_confirmation(
        self,
        session_id: str,
        tool_use_id: str,
        approved: bool,
        deny_message: Optional[str] = None,
    ) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base_url}/sessions/{session_id}/confirm",
                json={
                    "tool_use_id": tool_use_id,
                    "approved": approved,
                    "deny_message": deny_message,
                },
                headers=self._headers,
                timeout=30.0,
            )
