import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import EmailMessage, EmailResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class GoogleGmailProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://www.googleapis.com/gmail/v1"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def _build_message(self, msg: EmailMessage) -> dict:
        """Build RFC 2822 compliant email message with HTML support.

        Creates a MIME multipart/alternative message when HTML content is provided,
        allowing email clients to choose between plain text and HTML rendering.
        Falls back to simple plain text format when only text content is provided.

        Args:
            msg: EmailMessage with to, subject, body_text, body_html, cc, bcc, thread_id

        Returns:
            Dict with base64-encoded 'raw' message and optional 'threadId'
        """
        # Build MIME multipart message if HTML is provided
        if msg.body_html:
            mime_msg = MIMEMultipart("alternative")
            mime_msg["To"] = ", ".join(msg.to)
            mime_msg["Subject"] = msg.subject

            # Add optional cc/bcc headers
            if msg.cc:
                mime_msg["Cc"] = ", ".join(msg.cc)
            if msg.bcc:
                mime_msg["Bcc"] = ", ".join(msg.bcc)

            # Attach plain text part (fallback for non-HTML clients)
            if msg.body_text:
                text_part = MIMEText(msg.body_text, "plain", "utf-8")
                mime_msg.attach(text_part)

            # Attach HTML part (preferred rendering)
            html_part = MIMEText(msg.body_html, "html", "utf-8")
            mime_msg.attach(html_part)

            # Convert MIME message to RFC 2822 string and encode
            raw = mime_msg.as_string().encode("utf-8")
            b64 = base64.urlsafe_b64encode(raw).decode("utf-8")
        else:
            # Simple plain text message (backward compatible)
            headers = [
                f"To: {', '.join(msg.to)}",
                f"Subject: {msg.subject}",
                "MIME-Version: 1.0",
                "Content-Type: text/plain; charset=utf-8",
            ]
            if msg.cc:
                headers.append(f"Cc: {', '.join(msg.cc)}")
            if msg.bcc:
                headers.append(f"Bcc: {', '.join(msg.bcc)}")

            body = msg.body_text or ""
            raw = ("\r\n".join(headers) + "\r\n\r\n" + body).encode("utf-8")
            b64 = base64.urlsafe_b64encode(raw).decode("utf-8")

        # Build payload
        payload = {"raw": b64}
        if msg.thread_id:
            payload["threadId"] = msg.thread_id
        return payload

    def send_email(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/users/me/messages/send"
        payload = self._build_message(msg)
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"), thread_id=data.get("threadId"))
        except Exception as e:
            logger.exception("Gmail send_email failed")
            return EmailResult(status="error", error={"message": str(e)})

    def create_draft(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/users/me/drafts"
        payload = {"message": self._build_message(msg)}
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            draft = data.get("id") or (data.get("draft") or {}).get("id")
            thread = (data.get("message") or {}).get("threadId") or None
            return EmailResult(status="success", id=draft, thread_id=thread)
        except Exception as e:
            logger.exception("Gmail create_draft failed")
            return EmailResult(status="error", error={"message": str(e)})

    def send_draft(self, token: str, draft_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/users/me/drafts/send"
        payload = {"id": draft_id}
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"), thread_id=data.get("threadId"))
        except Exception as e:
            logger.exception("Gmail send_draft failed")
            return EmailResult(status="error", error={"message": str(e)})

    def search(
        self, token: str, query: str, max_results: int = 50, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[str]:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/users/me/messages"
        params = {"q": query, "maxResults": max_results}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return []
            data = resp.json()
            return [m.get("id") for m in data.get("messages", []) if m.get("id")]
        except Exception:
            return []

    def read(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/users/me/messages/{message_id}"
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
        url = f"{self.base_url}/users/me/messages/{message_id}/modify"
        payload = {"addLabelIds": add_labels or [], "removeLabelIds": remove_labels or []}
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"), thread_id=data.get("threadId"))
        except Exception as e:
            logger.exception("Gmail modify_labels failed")
            return EmailResult(status="error", error={"message": str(e)})

    def trash(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/users/me/messages/{message_id}/trash"
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers)
            if resp.status_code >= 400:
                return EmailResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EmailResult(status="success", id=data.get("id"), thread_id=data.get("threadId"))
        except Exception as e:
            logger.exception("Gmail trash failed")
            return EmailResult(status="error", error={"message": str(e)})

    def delete_permanently(
        self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/users/me/messages/{message_id}"
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (200, 204):
                return EmailResult(status="error", error=json_or_text(resp))
            return EmailResult(status="success", id=message_id)
        except Exception as e:
            logger.exception("Gmail delete_permanently failed")
            return EmailResult(status="error", error={"message": str(e)})
