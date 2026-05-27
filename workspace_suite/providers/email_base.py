from typing import Protocol, Tuple

from ..models import EmailMessage, EmailResult


class EmailProvider(Protocol):
    def send_email(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult: ...
    def create_draft(
        self, token: str, msg: EmailMessage, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult: ...
    def send_draft(
        self, token: str, draft_id: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult: ...
    def search(
        self, token: str, query: str, max_results: int = 50, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[str]: ...
    def read(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> dict: ...
    def modify_labels(
        self,
        token: str,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EmailResult: ...
    def trash(self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0) -> EmailResult: ...
    def delete_permanently(
        self, token: str, message_id: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> EmailResult: ...
