import unittest
from unittest.mock import MagicMock

from agno.tools import Toolkit

from toolkits.drive import DriveAuthError, DriveToolkit


class TestDriveToolkitInit(unittest.TestCase):
    """Tests for DriveToolkit initialization."""

    def test_init_with_auth_google(self):
        """Test initialization with Google Drive authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.user_id, "user123")
        self.assertEqual(toolkit.service_name, "google_drive")
        self.assertTrue(toolkit.auth)
        self.assertIsNotNone(toolkit._fetch_token_func)

    def test_init_with_auth_microsoft(self):
        """Test initialization with Microsoft OneDrive authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="microsoft_drive",
            tenant_id="tenant123",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "microsoft_drive")

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=False,
        )

        self.assertFalse(toolkit.auth)

    def test_is_toolkit_subclass(self):
        """Test that DriveToolkit is a Toolkit subclass."""
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=False,
        )
        self.assertIsInstance(toolkit, Toolkit)


class TestDriveToolkitTools(unittest.TestCase):
    """Tests for DriveToolkit tools registration."""

    def test_authenticated_toolkit_has_drive_tools(self):
        """Test that authenticated toolkit has drive tools."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Get tool names
        tool_names = [f.name for f in toolkit.functions.values()]

        # Should have drive tools
        self.assertIn("list_files", tool_names)
        self.assertIn("get_file_info", tool_names)

    def test_unauthenticated_toolkit_has_auth_required(self):
        """Test that unauthenticated toolkit has auth_required tool."""
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=False,
        )

        tool_names = [f.name for f in toolkit.functions.values()]
        self.assertIn("drive_auth_required", tool_names)


class TestDriveToolkitAuthRequired(unittest.TestCase):
    """Tests for auth_required functionality."""

    def test_auth_required_returns_card(self):
        """Test that auth_required returns proper card response."""
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=False,
        )

        # Find and call the auth_required function
        auth_func = None
        for func in toolkit.functions.values():
            if func.name == "drive_auth_required":
                auth_func = func
                break

        self.assertIsNotNone(auth_func)
        assert auth_func is not None  # for mypy
        result = auth_func.entrypoint()  # type: ignore[misc]

        self.assertIn("card", result)
        self.assertEqual(result["card"], "drive-auth-required")


class TestDriveToolkitErrorCard(unittest.TestCase):
    """Tests for error_card functionality."""

    def test_error_card_returns_error_response(self):
        """Test that error_card returns proper error response."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Call error_card method directly (it's a method on BaseToolkit, not a registered tool)
        result = toolkit.error_card(message="Test error message")

        self.assertIn("card", result)
        self.assertEqual(result["card"], "error")
        self.assertIn("message", result)


class TestDriveAuthError(unittest.TestCase):
    """Tests for DriveAuthError exception."""

    def test_drive_auth_error_is_runtime_error(self):
        """Test that DriveAuthError is a RuntimeError subclass."""
        error = DriveAuthError("Test error")
        self.assertIsInstance(error, RuntimeError)

    def test_drive_auth_error_message(self):
        """Test that DriveAuthError stores message correctly."""
        error = DriveAuthError("Authentication failed")
        self.assertEqual(str(error), "Authentication failed")


class TestDriveToolkitStr(unittest.TestCase):
    """Tests for DriveToolkit string representation."""

    def test_str_authenticated(self):
        """Test string representation for authenticated toolkit."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=True,
            fetch_token_func=fetch_token,
        )

        str_repr = str(toolkit)
        self.assertIn("DriveToolkit", str_repr)
        self.assertIn("google_drive", str_repr)
        self.assertIn("auth=True", str_repr)

    def test_str_unauthenticated(self):
        """Test string representation for unauthenticated toolkit."""
        toolkit = DriveToolkit(
            user_id="user123",
            service_name="google_drive",
            tenant_id="tenant123",
            auth=False,
        )

        str_repr = str(toolkit)
        self.assertIn("auth=False", str_repr)


if __name__ == "__main__":
    unittest.main()
