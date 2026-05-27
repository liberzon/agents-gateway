from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AttachmentMetadata:
    """Metadata for email attachment without downloading content."""

    filename: str
    mime_type: str
    part_id: str


@dataclass(frozen=True)
class EmailLinkData:
    """Lightweight email metadata for creating links and icons to Gmail."""

    message_id: str
    gmail_link: str
    subject: str
    from_address: str
    from_name: Optional[str]
    date: datetime
    snippet: str
    labels: list[str]
    is_unread: bool
    attachments: list[AttachmentMetadata]
    thread_id: Optional[str] = None


def transform_gmail_to_link_data(raw_message: Dict[str, Any]) -> EmailLinkData:
    """
    Transform Gmail API message response to EmailLinkData with web links.

    Args:
        raw_message: Raw Gmail API message object from messages.get()

    Returns:
        EmailLinkData with Gmail web link and display metadata

    Example Gmail API response structure:
        {
            "id": "18c5a1b2f3d4e5f6",
            "threadId": "18c5a1b2f3d4e5f6",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Hi, let's meet tomorrow...",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "Subject", "value": "Meeting tomorrow"},
                    {"name": "Date", "value": "Mon, 28 Oct 2025 10:30:00 -0700"}
                ],
                "parts": [
                    {
                        "partId": "0",
                        "mimeType": "text/plain",
                        "filename": "",
                        "body": {"size": 123}
                    },
                    {
                        "partId": "1",
                        "mimeType": "application/pdf",
                        "filename": "document.pdf",
                        "body": {"attachmentId": "ANGjdJ8..."}
                    }
                ]
            },
            "internalDate": "1730139000000"
        }
    """
    message_id = raw_message.get("id", "")
    thread_id = raw_message.get("threadId")
    labels = raw_message.get("labelIds", [])
    snippet = raw_message.get("snippet", "")

    # Construct Gmail web link based on labels
    gmail_section = "drafts" if "DRAFT" in labels else "inbox"
    gmail_link = f"https://mail.google.com/mail/u/0/#{gmail_section}/{message_id}"

    # Extract headers
    headers = {}
    payload = raw_message.get("payload", {})
    for header in payload.get("headers", []):
        headers[header["name"].lower()] = header["value"]

    # Parse From header for name and email
    from_value = headers.get("from", "")
    from_name = None
    from_address = from_value

    if "<" in from_value and ">" in from_value:
        # Format: "Alice Smith <alice@example.com>"
        from_name = from_value.split("<")[0].strip()
        from_address = from_value.split("<")[1].split(">")[0].strip()
    elif "@" in from_value:
        # Format: "alice@example.com"
        from_address = from_value.strip()

    # Parse date
    date_str = headers.get("date", "")
    try:
        from email.utils import parsedate_to_datetime

        date = parsedate_to_datetime(date_str)
    except Exception:
        # Fallback to internalDate (milliseconds since epoch)
        internal_date_ms = int(raw_message.get("internalDate", "0"))
        date = datetime.fromtimestamp(internal_date_ms / 1000)

    # Extract attachment metadata
    attachments = []
    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename", "")
        if filename:  # Only include parts with filenames (actual attachments)
            attachments.append(
                AttachmentMetadata(
                    filename=filename, mime_type=part.get("mimeType", ""), part_id=part.get("partId", "")
                )
            )

    # Check if unread
    is_unread = "UNREAD" in labels

    return EmailLinkData(
        message_id=message_id,
        gmail_link=gmail_link,
        subject=headers.get("subject", "(No subject)"),
        from_address=from_address,
        from_name=from_name,
        date=date,
        snippet=snippet,
        labels=labels,
        is_unread=is_unread,
        attachments=attachments,
        thread_id=thread_id,
    )
