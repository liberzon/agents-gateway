from typing import Optional, Sequence

from ..models import DriveFileResult
from ..providers.drive_base import DriveProvider


class DriveService:
    def __init__(self, provider: DriveProvider):
        self.provider = provider

    def upload(
        self,
        *,
        token: str,
        path: str,
        name: Optional[str] = None,
        parents: Optional[Sequence[str]] = None,
        mime_type: Optional[str] = None,
    ) -> DriveFileResult:
        return self.provider.upload_file(token=token, path=path, name=name, parents=parents, mime_type=mime_type)

    def update_content(
        self, *, token: str, file_id: str, path: str, mime_type: Optional[str] = None
    ) -> DriveFileResult:
        return self.provider.update_file_content(token=token, file_id=file_id, path=path, mime_type=mime_type)

    def create_folder(self, *, token: str, name: str, parents: Optional[Sequence[str]] = None) -> DriveFileResult:
        return self.provider.create_folder(token=token, name=name, parents=parents)

    def list(self, *, token: str, q: Optional[str] = None, page_size: int = 100) -> list[DriveFileResult]:
        return self.provider.list_files(token=token, q=q, page_size=page_size)

    def get_file_info(self, *, token: str, file_id: str) -> DriveFileResult:
        return self.provider.get_file_info(token=token, file_id=file_id)
