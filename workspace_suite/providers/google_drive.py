import io
import json
import logging
import os
from typing import Optional, Sequence, Tuple

import httpx

from ..config import ProviderConfig
from ..models import DriveFileResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class GoogleDriveProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://www.googleapis.com/drive/v3"
        self.upload_base = "https://www.googleapis.com/upload/drive/v3"

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
        metadata: dict[str, object] = {"name": name or os.path.basename(path)}
        if parents:
            metadata["parents"] = list(parents)

        boundary = "foo_bar_boundary"
        body = io.BytesIO()
        # metadata part
        body.write(f"--{boundary}\r\n".encode())
        body.write(b"Content-Type: application/json; charset=UTF-8\r\n\r\n")
        body.write(json.dumps(metadata).encode())
        body.write(b"\r\n")
        # file part
        body.write(f"--{boundary}\r\n".encode())
        body.write(f"Content-Type: {mime_type or 'application/octet-stream'}\r\n\r\n".encode())
        with open(path, "rb") as f:
            body.write(f.read())
        body.write(b"\r\n")
        body.write(f"--{boundary}--\r\n".encode())

        url = f"{self.upload_base}/files?uploadType=multipart"
        try:
            client = self._client(http_timeout)
            resp = client.post(
                url,
                headers={**headers, "Content-Type": f"multipart/related; boundary={boundary}"},
                content=body.getvalue(),
            )
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webViewLink")
            )
        except Exception as e:
            logger.exception("Drive upload_file failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def update_file_content(
        self,
        token: str,
        file_id: str,
        path: str,
        mime_type: Optional[str] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": mime_type or "application/octet-stream"}
        url = f"{self.upload_base}/files/{file_id}?uploadType=media"
        try:
            client = self._client(http_timeout)
            with open(path, "rb") as f:
                resp = client.patch(url, headers=headers, content=f.read())
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webViewLink")
            )
        except Exception as e:
            logger.exception("Drive update_file_content failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def create_folder(
        self,
        token: str,
        name: str,
        parents: Optional[Sequence[str]] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        metadata: dict[str, object] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parents:
            metadata["parents"] = list(parents)
        url = f"{self.base_url}/files"
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=metadata)
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return DriveFileResult(
                status="success", id=data.get("id"), name=data.get("name"), web_view_link=data.get("webViewLink")
            )
        except Exception as e:
            logger.exception("Drive create_folder failed")
            return DriveFileResult(status="error", error={"message": str(e)})

    def list_files(
        self,
        token: str,
        q: Optional[str] = None,
        page_size: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[DriveFileResult]:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"pageSize": page_size, "fields": "files(id,name,webViewLink)"}
        if q:
            params["q"] = q
        url = f"{self.base_url}/files"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [DriveFileResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            out: list[DriveFileResult] = []
            for f in data.get("files", []):
                out.append(
                    DriveFileResult(
                        status="success", id=f.get("id"), name=f.get("name"), web_view_link=f.get("webViewLink")
                    )
                )
            return out
        except Exception as e:
            logger.exception("Drive list_files failed")
            return [DriveFileResult(status="error", error={"message": str(e)})]

    def get_file_info(
        self,
        token: str,
        file_id: str,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult:
        headers = {"Authorization": f"Bearer {token}"}
        params = {"fields": "id,name,mimeType,webViewLink,createdTime,modifiedTime,size,owners/emailAddress"}
        url = f"{self.base_url}/files/{file_id}"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return DriveFileResult(status="error", error=json_or_text(resp))
            data = resp.json()

            # Extract owner email addresses
            owners = [owner.get("emailAddress") for owner in data.get("owners", []) if owner.get("emailAddress")]

            return DriveFileResult(
                status="success",
                id=data.get("id"),
                name=data.get("name"),
                mime_type=data.get("mimeType"),
                web_view_link=data.get("webViewLink"),
                created_time=data.get("createdTime"),
                modified_time=data.get("modifiedTime"),
                size=data.get("size"),
                owners=owners if owners else None,
            )
        except Exception as e:
            logger.exception("Drive get_file_info failed")
            return DriveFileResult(status="error", error={"message": str(e)})
