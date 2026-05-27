import logging
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import EmailMessage, EmailResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class MicrosoftMailProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://graph.microsoft.com/v1.0"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def _build_message(self, msg: EmailMessage) -> dict:
        content = msg.body_html or (msg.body_text or "")
        content_type = "HTML" if msg.body_html else "Text"
        return {
            "message": {
                "subject": msg.subject,
                "body": {"contentType": content_type, "content": content},
                "toRecipients": [{"emailAddress": {"address": a}} for a in msg.to],
                "ccRecipients": [{"emailAddress": {"address": a}} for a in msg.cc],
                "bccRecipients": [{"emailAddress": {"address": a}} for a in msg.bcc],
            },
            "saveToSentItems": True,
        }

    def send_email(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/sendMail"
        payload = self._build_message(msg)
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code not in (202, 200):
                return EmailResult(status="error", error=json_or_text(resp))
            return EmailResult(status="success", id=None)
        except Exception as e:
            logger.exception("Outlook send_email failed")
            return EmailResult(status="error", error={"message": str(e)})

    def create_draft(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/messages"
        payload = self._build_message(msg)["message"]
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"), thread_id=data.get("conversationId"))
        except Exception as e:
            logger.exception("Outlook create_draft failed")
            return EmailResult(status="error", error={"message": str(e)})

    def send_draft(self, token: str, draft_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/messages/{draft_id}/send"
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers)
            if resp.status_code not in (202, 200):
                return EmailResult(status="error", error=json_or_text(resp))
            return EmailResult(status="success", id=draft_id)
        except Exception as e:
            logger.exception("Outlook send_draft failed")
            return EmailResult(status="error", error={"message": str(e)})

    def search(
        self, token: str, query: str, max_results: int = 50, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[str]:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"$search": f'"{query}"', "$top": max_results}
        url = f"{self.base_url}/me/messages"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return []
            data = resp.json()
            return [m.get("id") for m in data.get("value", []) if m.get("id")]
        except Exception:
            return []

    def read(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/messages/{message_id}"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers)
            if resp.status_code >= 400:
                return {"error": json_or_text(resp)}
            return resp.json()
        except Exception as e:
            return {"error": {"message": str(e)}}

    def modify_labels(
        self,
        token: str,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/messages/{message_id}"
        categories = add_labels or []
        payload = {"categories": categories}
        try:
            client = self._client(http_timeout)
            resp = client.patch(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"))
        except Exception as e:
            logger.exception("Outlook modify_labels failed")
            return EmailResult(status="error", error={"message": str(e)})

    def trash(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/messages/{message_id}/move"
        payload = {"destinationId": "deleteditems"}
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"))
        except Exception as e:
            logger.exception("Outlook trash failed")
            return EmailResult(status="error", error={"message": str(e)})

    def delete_permanently(
        self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/messages/{message_id}"
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (204,):
                return EmailResult(status="error", error=json_or_text(resp))
            return EmailResult(status="success", id=message_id)
        except Exception as e:
            logger.exception("Outlook delete_permanently failed")
            return EmailResult(status="error", error={"message": str(e)})
