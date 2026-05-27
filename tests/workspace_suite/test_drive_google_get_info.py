import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.providers.google_drive import GoogleDriveProvider


class TestGoogleDriveGetFileInfo(unittest.TestCase):
    def test_get_file_info_success(self):
        """Test successful file info retrieval with all metadata fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            # Verify the request
            assert "files/file123" in str(request.url)
            assert request.headers["Authorization"] == "Bearer test_token"

            return httpx.Response(
                200,
                json={
                    "id": "file123",
                    "name": "document.pdf",
                    "mimeType": "application/pdf",
                    "webViewLink": "https://drive.google.com/file/d/file123/view",
                    "createdTime": "2025-10-20T10:00:00Z",
                    "modifiedTime": "2025-10-23T14:30:00Z",
                    "size": "245760",
                    "owners": [{"emailAddress": "user@example.com"}],
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file123")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.id, "file123")
        self.assertEqual(result.name, "document.pdf")
        self.assertEqual(result.mime_type, "application/pdf")
        self.assertEqual(result.web_view_link, "https://drive.google.com/file/d/file123/view")
        self.assertEqual(result.created_time, "2025-10-20T10:00:00Z")
        self.assertEqual(result.modified_time, "2025-10-23T14:30:00Z")
        self.assertEqual(result.size, "245760")
        self.assertEqual(result.owners, ["user@example.com"])

    def test_get_file_info_multiple_owners(self):
        """Test file info with multiple owners."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "file456",
                    "name": "shared.docx",
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "webViewLink": "https://drive.google.com/file/d/file456/view",
                    "createdTime": "2025-10-15T09:00:00Z",
                    "modifiedTime": "2025-10-20T16:45:00Z",
                    "size": "102400",
                    "owners": [
                        {"emailAddress": "owner1@example.com"},
                        {"emailAddress": "owner2@example.com"},
                    ],
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file456")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.owners, ["owner1@example.com", "owner2@example.com"])

    def test_get_file_info_no_owners(self):
        """Test file info when owners field is missing."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "file789",
                    "name": "orphan.txt",
                    "mimeType": "text/plain",
                    "webViewLink": "https://drive.google.com/file/d/file789/view",
                    "createdTime": "2025-09-01T12:00:00Z",
                    "modifiedTime": "2025-09-05T14:30:00Z",
                    "size": "1024",
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file789")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.owners)

    def test_get_file_info_folder(self):
        """Test file info for a folder (different MIME type)."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "folder123",
                    "name": "My Folder",
                    "mimeType": "application/vnd.google-apps.folder",
                    "webViewLink": "https://drive.google.com/drive/folders/folder123",
                    "createdTime": "2025-08-01T10:00:00Z",
                    "modifiedTime": "2025-10-01T11:00:00Z",
                    "owners": [{"emailAddress": "user@example.com"}],
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="folder123")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.mime_type, "application/vnd.google-apps.folder")
        self.assertIsNone(result.size)  # Folders don't have size

    def test_get_file_info_not_found(self):
        """Test file info when file doesn't exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                json={"error": {"code": 404, "message": "File not found"}},
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="nonexistent")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)

    def test_get_file_info_permission_denied(self):
        """Test file info with insufficient permissions."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"code": 403, "message": "Insufficient permissions"}},
            )

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="restricted")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)

    def test_get_file_info_network_error(self):
        """Test file info with network failure."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise Exception("Network connection failed")

        http_client = make_mock_client(handler)
        provider = GoogleDriveProvider(ProviderConfig(), http=http_client)

        result = provider.get_file_info(token="test_token", file_id="file123")

        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)
        self.assertIn("Network connection failed", str(result.error))


if __name__ == "__main__":
    unittest.main()
