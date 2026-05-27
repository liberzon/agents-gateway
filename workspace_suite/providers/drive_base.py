from typing import Optional, Protocol, Sequence, Tuple

from ..models import DriveFileResult


class DriveProvider(Protocol):
    def upload_file(
        self,
        token: str,
        path: str,
        name: Optional[str] = None,
        parents: Optional[Sequence[str]] = None,
        mime_type: Optional[str] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult: ...
    def update_file_content(
        self,
        token: str,
        file_id: str,
        path: str,
        mime_type: Optional[str] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult: ...
    def create_folder(
        self,
        token: str,
        name: str,
        parents: Optional[Sequence[str]] = None,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult: ...
    def read_file(
        self,
        token: str,
        file_id: str,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult: ...
    def list_files(
        self,
        token: str,
        q: Optional[str] = None,
        page_size: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> list[DriveFileResult]: ...
    def get_file_info(
        self,
        token: str,
        file_id: str,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> DriveFileResult: ...
