import logging
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import Contact, ContactResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class MicrosoftContactsProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://graph.microsoft.com/v1.0"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def create_contact(
        self, token: str, contact: Contact, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/contacts"
        payload = {
            "givenName": contact.given_name,
            "surname": contact.family_name or "",
            "emailAddresses": [{"address": e} for e in contact.emails],
            "businessPhones": list(contact.phones),
            "companyName": contact.company,
            "jobTitle": contact.job_title,
        }
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return ContactResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return ContactResult(status="success", resource_name=data.get("id"), etag=data.get("@odata.etag"))
        except Exception as e:
            logger.exception("MS Contacts create_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def update_contact(
        self, token: str, resource_name: str, patch: dict, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/contacts/{resource_name}"
        try:
            client = self._client(http_timeout)
            resp = client.patch(url, headers=headers, json=patch)
            if resp.status_code >= 400:
                return ContactResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return ContactResult(status="success", resource_name=data.get("id"), etag=data.get("@odata.etag"))
        except Exception as e:
            logger.exception("MS Contacts update_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def delete_contact(
        self, token: str, resource_name: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/contacts/{resource_name}"
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (204,):
                return ContactResult(status="error", error=json_or_text(resp))
            return ContactResult(status="success", resource_name=resource_name)
        except Exception as e:
            logger.exception("MS Contacts delete_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def list_contacts(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("displayName", "emailAddresses", "businessPhones"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[ContactResult]:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/contacts"
        params = {"$top": page_size, "$select": "id,displayName"}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [ContactResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[ContactResult] = []
            for it in data.get("value", []):
                out.append(ContactResult(status="success", resource_name=it.get("id"), etag=it.get("@odata.etag")))
            return out
        except Exception as e:
            logger.exception("MS Contacts list_contacts failed")
            return [ContactResult(status="error", error={"message": str(e)})]

    def search(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[ContactResult]:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/contacts"
        params = {"$search": f'"{query}"', "$top": page_size}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [ContactResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[ContactResult] = []
            for it in data.get("value", []):
                out.append(ContactResult(status="success", resource_name=it.get("id"), etag=it.get("@odata.etag")))
            return out
        except Exception as e:
            logger.exception("MS Contacts search failed")
            return [ContactResult(status="error", error={"message": str(e)})]

    def list_other_contacts(
        self, token: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[ContactResult]:
        """Microsoft doesn't have 'Other Contacts' concept - return empty list."""
        return []

    def fetch_contacts_raw(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("names", "emailAddresses", "phoneNumbers", "organizations"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> tuple[list[dict], str | None]:
        """Fetch raw contact data from Microsoft Contacts for custom processing."""
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/contacts"
        params = {"$top": page_size}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return ([], f"Microsoft Contacts API returned {resp.status_code}")
            data = resp.json()
            return (data.get("value", []), None)
        except Exception as e:
            logger.exception("MS Contacts fetch_contacts_raw failed")
            return ([], str(e))

    def fetch_other_contacts_raw(
        self, token: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> tuple[list[dict], str | None]:
        """Microsoft doesn't have 'Other Contacts' concept - return empty list."""
        return ([], None)

    def search_contacts_raw(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> tuple[list[dict], str | None]:
        """Search Microsoft Contacts and return raw contact data for custom processing."""
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/contacts"
        params = {"$search": f'"{query}"', "$top": page_size}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return ([], f"Microsoft Search API returned {resp.status_code}")
            data = resp.json()
            return (data.get("value", []), None)
        except Exception as e:
            logger.exception("MS Contacts search_contacts_raw failed")
            return ([], str(e))
