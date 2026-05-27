import logging
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import Contact, ContactResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class GoogleContactsProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://people.googleapis.com/v1"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def create_contact(
        self, token: str, contact: Contact, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/people:createContact"
        payload = {
            "names": [{"givenName": contact.given_name, "familyName": contact.family_name or ""}],
            "emailAddresses": [{"value": e} for e in contact.emails],
            "phoneNumbers": [{"value": p} for p in contact.phones],
            "organizations": [{"name": contact.company, "title": contact.job_title}]
            if contact.company or contact.job_title
            else None,
        }
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return ContactResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return ContactResult(status="success", resource_name=data.get("resourceName"), etag=data.get("etag"))
        except Exception as e:
            logger.exception("Contacts create_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def update_contact(
        self, token: str, resource_name: str, patch: dict, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/{resource_name}:updateContact"
        params = {
            "updatePersonFields": ",".join(patch.keys()) if patch else "names,emailAddresses,phoneNumbers,organizations"
        }
        try:
            client = self._client(http_timeout)
            resp = client.patch(url, headers=headers, params=params, json=patch)
            if resp.status_code >= 400:
                return ContactResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return ContactResult(status="success", resource_name=data.get("resourceName"), etag=data.get("etag"))
        except Exception as e:
            logger.exception("Contacts update_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def delete_contact(
        self, token: str, resource_name: str, http_timeout: float | Tuple[float, float] = 15.0
    ) -> ContactResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/{resource_name}:deleteContact"
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (200, 204):
                return ContactResult(status="error", error=json_or_text(resp))
            return ContactResult(status="success", resource_name=resource_name)
        except Exception as e:
            logger.exception("Contacts delete_contact failed")
            return ContactResult(status="error", error={"message": str(e)})

    def list_contacts(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("names", "emailAddresses", "phoneNumbers"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[ContactResult]:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"pageSize": page_size, "personFields": ",".join(person_fields)}
        url = f"{self.base_url}/people/me/connections"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [ContactResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[ContactResult] = []
            for p in data.get("connections", []):
                out.append(ContactResult(status="success", resource_name=p.get("resourceName"), etag=p.get("etag")))
            return out
        except Exception as e:
            logger.exception("Contacts list_contacts failed")
            return [ContactResult(status="error", error={"message": str(e)})]

    def list_other_contacts(
        self,
        token: str,
        page_size: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[ContactResult]:
        """List 'Other Contacts' (auto-saved contacts from Gmail interactions)."""
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "pageSize": page_size,
            "readMask": "names,emailAddresses,phoneNumbers",
        }
        url = f"{self.base_url}/otherContacts"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [ContactResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[ContactResult] = []
            for p in data.get("otherContacts", []):
                out.append(ContactResult(status="success", resource_name=p.get("resourceName"), etag=p.get("etag")))
            return out
        except Exception as e:
            logger.exception("Contacts list_other_contacts failed")
            return [ContactResult(status="error", error={"message": str(e)})]

    def fetch_contacts_raw(
        self,
        token: str,
        page_size: int = 100,
        person_fields: tuple[str, ...] = ("names", "emailAddresses", "phoneNumbers"),
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> tuple[list[dict], str | None]:
        """
        Fetch raw contact data from 'My Contacts' for custom processing.

        Returns:
            Tuple of (list of person dictionaries, error message or None)
        """
        headers = {"Authorization": f"Bearer {token}"}
        params = {"pageSize": page_size, "personFields": ",".join(person_fields)}
        url = f"{self.base_url}/people/me/connections"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                logger.warning(f"My Contacts API returned error status {resp.status_code}")
                return ([], f"My Contacts API returned {resp.status_code}")
            data = resp.json()
            contacts = data.get("connections", [])
            logger.info(f"Retrieved {len(contacts)} contacts from My Contacts (page_size={page_size})")
            return (contacts, None)
        except Exception as e:
            logger.exception("Contacts fetch_contacts_raw failed")
            return ([], str(e))

    def fetch_other_contacts_raw(
        self,
        token: str,
        page_size: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> tuple[list[dict], str | None]:
        """
        Fetch raw 'Other Contacts' data for custom processing.

        Note: Other Contacts only support a limited set of fields (names, emailAddresses, phoneNumbers, photos, metadata).
        Organizations field is not available for Other Contacts.

        Returns:
            Tuple of (list of person dictionaries, error message or None)
        """
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "pageSize": page_size,
            "readMask": "names,emailAddresses,phoneNumbers",
        }
        url = f"{self.base_url}/otherContacts"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                logger.warning(f"Other Contacts API returned error status {resp.status_code}")
                return ([], f"Other Contacts API returned {resp.status_code}")
            data = resp.json()
            other_contacts = data.get("otherContacts", [])
            logger.info(f"Retrieved {len(other_contacts)} contacts from Other Contacts (page_size={page_size})")
            return (other_contacts, None)
        except Exception as e:
            logger.exception("Contacts fetch_other_contacts_raw failed")
            return ([], str(e))

    def search(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> list[ContactResult]:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"query": query, "readMask": "names,emailAddresses,phoneNumbers", "pageSize": page_size}
        url = f"{self.base_url}/people:searchContacts"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [ContactResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[ContactResult] = []
            for p in data.get("results", []):
                person = p.get("person", {})
                out.append(
                    ContactResult(status="success", resource_name=person.get("resourceName"), etag=person.get("etag"))
                )
            return out
        except Exception as e:
            logger.exception("Contacts search failed")
            return [ContactResult(status="error", error={"message": str(e)})]

    def search_contacts_raw(
        self, token: str, query: str, page_size: int = 100, http_timeout: float | Tuple[float, float] = 15.0
    ) -> tuple[list[dict], str | None]:
        """
        Search My Contacts and return raw person data for custom processing.

        Returns:
            Tuple of (list of person dictionaries, error message or None)
        """
        headers = {"Authorization": f"Bearer {token}"}
        params = {"query": query, "readMask": "names,emailAddresses,phoneNumbers", "pageSize": page_size}
        url = f"{self.base_url}/people:searchContacts"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return ([], f"Search My Contacts API returned {resp.status_code}")
            data = resp.json()
            # searchContacts returns results wrapped in "person" objects
            results = data.get("results", [])
            persons = [item.get("person", {}) for item in results]
            return (persons, None)
        except Exception as e:
            logger.exception("Contacts search_contacts_raw failed")
            return ([], str(e))
