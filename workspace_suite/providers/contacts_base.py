from typing import Protocol, Tuple

from ..models import Contact, ContactResult


class ContactsProvider(Protocol):
    def create_contact(
        self, token: str, contact: Contact, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult: ...
    def update_contact(
        self, token: str, resource_name: str, patch: dict, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult: ...
    def delete_contact(
        self, token: str, resource_name: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult: ...
    def list_contacts(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("names", "emailAddresses", "phoneNumbers"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[ContactResult]: ...
    def search(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[ContactResult]: ...
    def list_other_contacts(
        self, token: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[ContactResult]: ...
    def fetch_contacts_raw(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("names", "emailAddresses", "phoneNumbers"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> tuple[list[dict], str | None]: ...
    def fetch_other_contacts_raw(
        self, token: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> tuple[list[dict], str | None]: ...
    def search_contacts_raw(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> tuple[list[dict], str | None]: ...
