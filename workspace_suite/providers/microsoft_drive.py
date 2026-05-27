import logging
import os
from typing import Optional, Sequence, Tuple

import httpx

from ..config import ProviderConfig
from ..models import DriveFileResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class MicrosoftDriveProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://graph.microsoft.com/v1.0"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def upload_file(
        self,
        token: str,
        path: str,
        name: Optional[str] = None,
        parents: Optional[Sequence[str]] = None,
        mime_type: Optional[str] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}"}
        fname = name or os.path.basename(path)
        url = f"{self.base_url}/me/drive/root:/{fname}:/content"
        try:
            client = self._client(http_timeout)
            with open(path, "rb") as f:
                resp = client.put(url, headers=headers, content=f.read())
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webUrl")
            )
        except Exception as e:
            logger.exception("OneDrive upload_file failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def update_file_content(
        self,
        token: str,
        file_id: str,
        path: str,
        mime_type: Optional[str] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/drive/items/{file_id}/content"
        try:
            client = self._client(http_timeout)
            with open(path, "rb") as f:
                resp = client.put(url, headers=headers, content=f.read())
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webUrl")
            )
        except Exception as e:
            logger.exception("OneDrive update_file_content failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def create_folder(
        self,
        token: str,
        name: str,
        parents: Optional[Sequence[str]] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/drive/root/children"
        payload = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webUrl")
            )
        except Exception as e:
            logger.exception("OneDrive create_folder failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def list_files(
        self,
        token: str,
        q: Optional[str] = None,
        page_size: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[DriveFileResult]:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/drive/root/children"
        params = {"$top": page_size, "$select": "id,name,webUrl"}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [DriveFileResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[DriveFileResult] = []
            for it in data.get("value", []):
                out.append(
                    DriveFileResult(
                        status="success", id=it.get("id"), name=it.get("name"), web_view_link=it.get("webUrl")
                    )
                )
            return out
        except Exception as e:
            logger.exception("OneDrive list_files failed")
            return [DriveFileResult(status="error", error={"message": str(e)})]

    def get_file_info(
        self,
        token: str,
        file_id: str,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/me/drive/items/{file_id}"
        params = {"$select": "id,name,file,webUrl,createdDateTime,lastModifiedDateTime,size,createdBy"}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()

            # Extract MIME type from file.mimeType
            mime_type = None
            if "file" in data and "mimeType" in data["file"]:
                mime_type = data["file"]["mimeType"]

            # Extract owner email from createdBy.user.email
            owners = None
            if "createdBy" in data and "user" in data["createdBy"]:
                email = data["createdBy"]["user"].get("email")
                if email:
                    owners = [email]

            return DriveFileResult(
                status="success",
                id=data.get("id"),
                name=data.get("name"),
                mime_type=mime_type,
                web_view_link=data.get("webUrl"),
                created_time=data.get("createdDateTime"),
                modified_time=data.get("lastModifiedDateTime"),
                size=str(data.get("size")) if data.get("size") is not None else None,
                owners=owners,
            )
        except Exception as e:
            logger.exception("OneDrive get_file_info failed")
            return DriveFileResult(status="error", error={"message": str(e)})
