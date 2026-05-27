from ..models import EmailMessage, EmailResult
from ..providers.email_base import EmailProvider


class EmailService:
    """
    Unified email service.
    Works with both Gmail (Google) and Outlook Mail (Microsoft) providers.
    """

    def __init__(self, provider: EmailProvider):
        self.provider = provider

    def send(self, *, token: str, msg: EmailMessage) -> EmailResult:
        return self.provider.send_email(token=token, msg=msg)

    def draft(self, *, token: str, msg: EmailMessage) -> EmailResult:
        return self.provider.create_draft(token=token, msg=msg)

    def send_draft(self, *, token: str, draft_id: str) -> EmailResult:
        return self.provider.send_draft(token=token, draft_id=draft_id)

    def search(self, *, token: str, query: str, max_results: int = 50) -> list[str]:
        return self.provider.search(token=token, query=query, max_results=max_results)

    def read(self, *, token: str, message_id: str) -> dict:
        return self.provider.read(token=token, message_id=message_id)

    def modify_labels(
        self,
        *,
        token: str,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> EmailResult:
        return self.provider.modify_labels(
            token=token, message_id=message_id, add_labels=add_labels, remove_labels=remove_labels
        )

    def trash(self, *, token: str, message_id: str) -> EmailResult:
        return self.provider.trash(token=token, message_id=message_id)

    def delete_permanently(self, *, token: str, message_id: str) -> EmailResult:
        return self.provider.delete_permanently(token=token, message_id=message_id)
