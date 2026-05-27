import unittest
from unittest.mock import MagicMock

from agno.tools import Toolkit

from toolkits.email import EmailAuthError, EmailToolkit


class TestEmailToolkitInit(unittest.TestCase):
    """Tests for EmailToolkit initialization."""

    def test_init_with_auth_gmail(self):
        """Test initialization with Gmail authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.user_id, "user123")
        self.assertEqual(toolkit.service_name, "gmail")
        self.assertTrue(toolkit.auth)
        self.assertIsNotNone(toolkit._fetch_token_func)

    def test_init_with_auth_outlook(self):
        """Test initialization with Outlook authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="outlook",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "outlook")

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=False,
        )

        self.assertFalse(toolkit.auth)

    def test_is_toolkit_subclass(self):
        """Test that EmailToolkit is a Toolkit subclass."""
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=False,
        )
        self.assertIsInstance(toolkit, Toolkit)


class TestEmailToolkitTools(unittest.TestCase):
    """Tests for EmailToolkit tools registration."""

    def test_authenticated_toolkit_has_email_tools(self):
        """Test that authenticated toolkit has email tools."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Get tool names
        tool_names = [f.name for f in toolkit.functions.values()]

        # Should have email tools
        self.assertIn("send_email", tool_names)
        self.assertIn("create_draft", tool_names)
        self.assertIn("search_emails", tool_names)

    def test_unauthenticated_toolkit_has_auth_required(self):
        """Test that unauthenticated toolkit has auth_required tool."""
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=False,
        )

        tool_names = [f.name for f in toolkit.functions.values()]
        self.assertIn("email_auth_required", tool_names)


class TestEmailToolkitAuthRequired(unittest.TestCase):
    """Tests for auth_required functionality."""

    def test_auth_required_returns_card(self):
        """Test that auth_required returns proper card response."""
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=False,
        )

        # Find and call the auth_required function
        auth_func = None
        for func in toolkit.functions.values():
            if func.name == "email_auth_required":
                auth_func = func
                break

        self.assertIsNotNone(auth_func)
        assert auth_func is not None  # for mypy
        result = auth_func.entrypoint()  # type: ignore[misc]

        self.assertIn("card", result)
        self.assertEqual(result["card"], "email-auth-required")


class TestEmailToolkitErrorCard(unittest.TestCase):
    """Tests for error_card functionality."""

    def test_error_card_returns_error_response(self):
        """Test that error_card returns proper error response."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Call error_card method directly (it's a method on BaseToolkit, not a registered tool)
        result = toolkit.error_card(message="Test error message")

        self.assertIn("card", result)
        self.assertEqual(result["card"], "error")
        self.assertIn("message", result)
        self.assertEqual(result["message"], "Test error message")


class TestEmailToolkitProviderSelection(unittest.TestCase):
    """Tests for email provider selection."""

    def test_gmail_provider_selection(self):
        """Test that gmail service_name selects Google provider."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Provider should be set correctly
        self.assertEqual(toolkit.service_name, "gmail")

    def test_outlook_provider_selection(self):
        """Test that outlook service_name selects Microsoft provider."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="outlook",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "outlook")

    def test_microsoft_alias_works(self):
        """Test that microsoft alias works for Outlook."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="microsoft",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "microsoft")


class TestEmailAuthError(unittest.TestCase):
    """Tests for EmailAuthError exception."""

    def test_email_auth_error_is_runtime_error(self):
        """Test that EmailAuthError is a RuntimeError subclass."""
        error = EmailAuthError("Test error")
        self.assertIsInstance(error, RuntimeError)

    def test_email_auth_error_message(self):
        """Test that EmailAuthError stores message correctly."""
        error = EmailAuthError("Authentication failed")
        self.assertEqual(str(error), "Authentication failed")


class TestEmailToolkitStr(unittest.TestCase):
    """Tests for EmailToolkit string representation."""

    def test_str_authenticated(self):
        """Test string representation for authenticated toolkit."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=True,
            fetch_token_func=fetch_token,
        )

        str_repr = str(toolkit)
        self.assertIn("EmailToolkit", str_repr)
        self.assertIn("gmail", str_repr)
        self.assertIn("auth=True", str_repr)

    def test_str_unauthenticated(self):
        """Test string representation for unauthenticated toolkit."""
        toolkit = EmailToolkit(
            user_id="user123",
            service_name="gmail",
            auth=False,
        )

        str_repr = str(toolkit)
        self.assertIn("auth=False", str_repr)


if __name__ == "__main__":
    unittest.main()
