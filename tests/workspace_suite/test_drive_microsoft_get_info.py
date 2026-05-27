import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.providers.microsoft_drive import MicrosoftDriveProvider


class TestMicrosoftDriveGetFileInfo(unittest.TestCase):
    def test_get_file_info_success(self):
        """Test successful file info retrieval with all metadata fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            # Verify the request
            assert "items/file123" in str(request.url)
            assert request.headers["Authorization"] == "Bearer test_token"

            return httpx.Response(
                200,
                json={
                    "id": "file123",
                    "name": "document.pdf",
                    "file": {"mimeType": "application/pdf"},
                    "webUrl": "https://onedrive.live.com/?cid=abc123",
                    "createdDateTime": "2025-10-20T10:00:00Z",
                    "lastModifiedDateTime": "2025-10-23T14:30:00Z",
                    "size": 245760,
                    "createdBy": {"user": {"email": "user@example.com"}},
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file123")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.id, "file123")
        self.assertEqual(result.name, "document.pdf")
        self.assertEqual(result.mime_type, "application/pdf")
        self.assertEqual(result.web_view_link, "https://onedrive.live.com/?cid=abc123")
        self.assertEqual(result.created_time, "2025-10-20T10:00:00Z")
        self.assertEqual(result.modified_time, "2025-10-23T14:30:00Z")
        self.assertEqual(result.size, "245760")
        self.assertEqual(result.owners, ["user@example.com"])

    def test_get_file_info_no_mime_type(self):
        """Test file info when file object doesn't contain mimeType."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "file456",
                    "name": "unknown.bin",
                    "webUrl": "https://onedrive.live.com/?cid=def456",
                    "createdDateTime": "2025-10-15T09:00:00Z",
                    "lastModifiedDateTime": "2025-10-20T16:45:00Z",
                    "size": 102400,
                    "createdBy": {"user": {"email": "owner@example.com"}},
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file456")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.mime_type)

    def test_get_file_info_no_owner(self):
        """Test file info when createdBy field is missing."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "file789",
                    "name": "orphan.txt",
                    "file": {"mimeType": "text/plain"},
                    "webUrl": "https://onedrive.live.com/?cid=ghi789",
                    "createdDateTime": "2025-09-01T12:00:00Z",
                    "lastModifiedDateTime": "2025-09-05T14:30:00Z",
                    "size": 1024,
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file789")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.owners)

    def test_get_file_info_folder(self):
        """Test file info for a folder."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "folder123",
                    "name": "My Folder",
                    "folder": {"childCount": 5},
                    "webUrl": "https://onedrive.live.com/?cid=folder123",
                    "createdDateTime": "2025-08-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-10-01T11:00:00Z",
                    "createdBy": {"user": {"email": "user@example.com"}},
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="folder123")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.name, "My Folder")
        self.assertIsNone(result.mime_type)  # Folders don't have file.mimeType
        self.assertIsNone(result.size)  # Folders don't have size

    def test_get_file_info_zero_size(self):
        """Test file info with zero-byte file."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "empty_file",
                    "name": "empty.txt",
                    "file": {"mimeType": "text/plain"},
                    "webUrl": "https://onedrive.live.com/?cid=empty",
                    "createdDateTime": "2025-10-23T10:00:00Z",
                    "lastModifiedDateTime": "2025-10-23T10:00:00Z",
                    "size": 0,
                    "createdBy": {"user": {"email": "user@example.com"}},
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="empty_file")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.size, "0")

    def test_get_file_info_not_found(self):
        """Test file info when file doesn't exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                json={"error": {"code": "itemNotFound", "message": "The resource could not be found"}},
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="nonexistent")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)

    def test_get_file_info_permission_denied(self):
        """Test file info with insufficient permissions."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"code": "accessDenied", "message": "Access denied"}},
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="restricted")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)

    def test_get_file_info_network_error(self):
        """Test file info with network failure."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise Exception("Network connection failed")

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file123")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)
        self.assertIn("Network connection failed", str(result.error))


if __name__ == "__main__":
    unittest.main()
