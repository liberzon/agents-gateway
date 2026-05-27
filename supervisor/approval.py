"""Approval notification and decision routing for satellite agent HITL flows.

When a worker agent (Claude Code, managed agent) needs approval for a tool call,
this module handles notifying the user via configured notification plugins and
collecting their decision.

Notification plugins are provider-agnostic — any plugin that implements the
NotificationPlugin interface can be registered (Telegram, Slack, Discord,
WhatsApp, email, webhook, Claude Code plugins, custom). The system also
supports polling via the /v2/approvals API for UI-based approval.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ApprovalNotification(BaseModel):
    """Sent to notification plugins when a tool call needs human review."""

    job_id: str
    run_id: Optional[str] = None
    team_id: Optional[str] = None
    worker_name: str = ""
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "medium"
    reason: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    approve_url: Optional[str] = None
    deny_url: Optional[str] = None


class ApprovalConfig(BaseModel):
    """Configuration for approval notification."""

    plugins: List[str] = Field(default_factory=list)  # Plugin names to notify (e.g., ["telegram", "slack"])
    api_base_url: str = "http://localhost:8000"
    # Fallback: if no plugins configured, use polling only
    polling_enabled: bool = True


# ---------------------------------------------------------------------------
# Notification Plugin Interface
# ---------------------------------------------------------------------------


class NotificationPlugin(ABC):
    """Base class for approval notification plugins.

    Implement this to add new notification channels (Discord, WhatsApp, email, etc.).
    Plugins are registered with the global registry and selected via ApprovalConfig.plugins.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name (e.g., 'telegram', 'discord', 'slack')."""

    @abstractmethod
    async def send_approval_request(
        self,
        notification: ApprovalNotification,
        config: Dict[str, Any],
    ) -> bool:
        """Send an approval notification. Returns True if sent successfully."""

    async def send_decision_confirmation(
        self,
        job_id: str,
        approved: bool,
        config: Dict[str, Any],
    ) -> None:
        """Optionally notify the channel that a decision was made."""


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

_plugin_registry: Dict[str, NotificationPlugin] = {}


def register_plugin(plugin: NotificationPlugin) -> None:
    """Register a notification plugin."""
    _plugin_registry[plugin.name] = plugin
    logger.info(f"Registered approval notification plugin: {plugin.name}")


def get_plugin(name: str) -> Optional[NotificationPlugin]:
    """Get a registered plugin by name."""
    return _plugin_registry.get(name)


def list_plugins() -> List[str]:
    """List all registered plugin names."""
    return list(_plugin_registry.keys())


# ---------------------------------------------------------------------------
# Built-in Plugins
# ---------------------------------------------------------------------------


class WebhookPlugin(NotificationPlugin):
    """Send approval requests via HTTP webhook."""

    @property
    def name(self) -> str:
        return "webhook"

    async def send_approval_request(self, notification: ApprovalNotification, config: Dict[str, Any]) -> bool:
        url = config.get("url")
        if not url:
            logger.warning("Webhook plugin: no URL configured")
            return False
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json=notification.model_dump(mode="json"),
                    headers=config.get("headers", {}),
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False


class TelegramPlugin(NotificationPlugin):
    """Send approval requests via Telegram bot API.

    Config keys: bot_token, chat_id
    Or uses the Claude Code Telegram plugin if available.
    """

    @property
    def name(self) -> str:
        return "telegram"

    async def send_approval_request(self, notification: ApprovalNotification, config: Dict[str, Any]) -> bool:
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")

        if not bot_token or not chat_id:
            logger.warning("Telegram plugin: bot_token and chat_id required")
            return False

        message = _format_message(notification, config.get("api_base_url", ""))
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "reply_markup": {
                            "inline_keyboard": [
                                [
                                    {"text": "Approve", "callback_data": f"approve:{notification.job_id}"},
                                    {"text": "Deny", "callback_data": f"deny:{notification.job_id}"},
                                ]
                            ]
                        },
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False


class SlackPlugin(NotificationPlugin):
    """Send approval requests via Slack webhook or API."""

    @property
    def name(self) -> str:
        return "slack"

    async def send_approval_request(self, notification: ApprovalNotification, config: Dict[str, Any]) -> bool:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.warning("Slack plugin: webhook_url required")
            return False

        message = _format_message(notification, config.get("api_base_url", ""))
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={"text": message}, timeout=10.0)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False


class DiscordPlugin(NotificationPlugin):
    """Send approval requests via Discord webhook."""

    @property
    def name(self) -> str:
        return "discord"

    async def send_approval_request(self, notification: ApprovalNotification, config: Dict[str, Any]) -> bool:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.warning("Discord plugin: webhook_url required")
            return False

        message = _format_message(notification, config.get("api_base_url", ""))
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json={"content": message}, timeout=10.0)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False


class WhatsAppPlugin(NotificationPlugin):
    """Send approval requests via WhatsApp Business API."""

    @property
    def name(self) -> str:
        return "whatsapp"

    async def send_approval_request(self, notification: ApprovalNotification, config: Dict[str, Any]) -> bool:
        phone_number_id = config.get("phone_number_id")
        access_token = config.get("access_token")
        recipient = config.get("recipient")

        if not all([phone_number_id, access_token, recipient]):
            logger.warning("WhatsApp plugin: phone_number_id, access_token, recipient required")
            return False

        message = _format_message(notification, config.get("api_base_url", ""))
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v17.0/{phone_number_id}/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": recipient,
                        "type": "text",
                        "text": {"body": message},
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"WhatsApp notification failed: {e}")
            return False


# Register built-in plugins
register_plugin(WebhookPlugin())
register_plugin(TelegramPlugin())
register_plugin(SlackPlugin())
register_plugin(DiscordPlugin())
register_plugin(WhatsAppPlugin())


# ---------------------------------------------------------------------------
# In-memory pending approvals store
# ---------------------------------------------------------------------------

_pending_approvals: Dict[str, ApprovalNotification] = {}
_approval_decisions: Dict[str, Dict[str, Any]] = {}
_approval_events: Dict[str, asyncio.Event] = {}


def register_pending_approval(notification: ApprovalNotification) -> None:
    """Register a pending approval request."""
    _pending_approvals[notification.job_id] = notification
    _approval_events[notification.job_id] = asyncio.Event()
    logger.info(f"Registered pending approval for job {notification.job_id}: {notification.tool_name}")


def submit_decision(
    job_id: str, approved: bool, reason: str = "", modified_args: Optional[Dict[str, Any]] = None
) -> bool:
    """Submit an approval decision for a pending request."""
    if job_id not in _pending_approvals:
        logger.warning(f"No pending approval for job {job_id}")
        return False

    _approval_decisions[job_id] = {
        "approved": approved,
        "reason": reason,
        "modified_args": modified_args,
        "decided_at": datetime.utcnow().isoformat(),
    }

    event = _approval_events.get(job_id)
    if event:
        event.set()

    _pending_approvals.pop(job_id, None)
    logger.info(f"Decision for job {job_id}: {'approved' if approved else 'denied'}")
    return True


async def wait_for_decision(job_id: str, timeout: float = 300.0) -> Optional[Dict[str, Any]]:
    """Wait for an approval decision. Returns the decision or None on timeout."""
    event = _approval_events.get(job_id)
    if not event:
        return _approval_decisions.get(job_id)

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Approval timeout for job {job_id}")
        return None

    decision = _approval_decisions.pop(job_id, None)
    _approval_events.pop(job_id, None)
    return decision


def get_pending_approvals() -> List[ApprovalNotification]:
    """Get all pending approval requests (for polling / UI)."""
    return list(_pending_approvals.values())


def get_pending_approval(job_id: str) -> Optional[ApprovalNotification]:
    """Get a specific pending approval request."""
    return _pending_approvals.get(job_id)


# ---------------------------------------------------------------------------
# Notification dispatcher
# ---------------------------------------------------------------------------


async def notify_approval_needed(
    notification: ApprovalNotification,
    config: ApprovalConfig,
    plugin_configs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
    """Send approval notification via all configured plugins.

    Args:
        notification: The approval request
        config: Approval configuration (which plugins to use)
        plugin_configs: Per-plugin config dicts (e.g., {"telegram": {"bot_token": "...", "chat_id": "..."}})
    """
    register_pending_approval(notification)

    # Generate approve/deny URLs
    notification.approve_url = f"{config.api_base_url}/v2/approvals/{notification.job_id}/approve"
    notification.deny_url = f"{config.api_base_url}/v2/approvals/{notification.job_id}/deny"

    if not config.plugins:
        logger.info(f"No notification plugins configured — approval for {notification.job_id} available via polling")
        return True

    plugin_configs = plugin_configs or {}
    sent = False

    for plugin_name in config.plugins:
        plugin = get_plugin(plugin_name)
        if not plugin:
            logger.warning(f"Unknown notification plugin: {plugin_name}")
            continue

        pconfig = plugin_configs.get(plugin_name, {})
        pconfig["api_base_url"] = config.api_base_url

        try:
            success = await plugin.send_approval_request(notification, pconfig)
            if success:
                sent = True
                logger.info(f"Approval notification sent via {plugin_name} for job {notification.job_id}")
        except Exception as e:
            logger.error(f"Plugin {plugin_name} failed: {e}")

    return sent


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


def _format_message(notification: ApprovalNotification, api_base_url: str = "") -> str:
    """Format a human-readable approval message for any channel."""
    approve_url = notification.approve_url or f"{api_base_url}/v2/approvals/{notification.job_id}/approve"
    deny_url = notification.deny_url or f"{api_base_url}/v2/approvals/{notification.job_id}/deny"
    args_preview = json.dumps(notification.tool_args, indent=2)[:300]

    return (
        f"*Approval Required*\n\n"
        f"*Worker:* {notification.worker_name}\n"
        f"*Tool:* `{notification.tool_name}`\n"
        f"*Risk:* {notification.risk_level}\n"
        f"*Reason:* {notification.reason}\n\n"
        f"*Arguments:*\n```\n{args_preview}\n```\n\n"
        f"Approve: {approve_url}\n"
        f"Deny: {deny_url}\n\n"
        f"_Job: {notification.job_id}_"
    )
