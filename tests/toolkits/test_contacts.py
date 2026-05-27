import unittest
from unittest.mock import MagicMock

from agno.tools import Toolkit

from toolkits.contacts import ContactsAuthError, ContactsToolkit


class TestContactsToolkitInit(unittest.TestCase):
    """Tests for ContactsToolkit initialization."""

    def test_init_with_auth_google(self):
        """Test initialization with Google Contacts authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.user_id, "user123")
        self.assertEqual(toolkit.service_name, "google_contacts")
        self.assertTrue(toolkit.auth)
        self.assertIsNotNone(toolkit._fetch_token_func)

    def test_init_with_auth_microsoft(self):
        """Test initialization with Microsoft Contacts authentication."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="microsoft_contacts",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "microsoft_contacts")

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=False,
        )

        self.assertFalse(toolkit.auth)

    def test_is_toolkit_subclass(self):
        """Test that ContactsToolkit is a Toolkit subclass."""
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=False,
        )
        self.assertIsInstance(toolkit, Toolkit)


class TestContactsToolkitTools(unittest.TestCase):
    """Tests for ContactsToolkit tools registration."""

    def test_authenticated_toolkit_has_contacts_tools(self):
        """Test that authenticated toolkit has contacts tools."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Get tool names
        tool_names = [f.name for f in toolkit.functions.values()]

        # Should have contacts tools
        self.assertIn("create_contact", tool_names)
        self.assertIn("list_contacts", tool_names)
        self.assertIn("search_contacts", tool_names)

    def test_unauthenticated_toolkit_has_auth_required(self):
        """Test that unauthenticated toolkit has auth_required tool."""
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=False,
        )

        tool_names = [f.name for f in toolkit.functions.values()]
        self.assertIn("contacts_auth_required", tool_names)


class TestContactsToolkitAuthRequired(unittest.TestCase):
    """Tests for auth_required functionality."""

    def test_auth_required_returns_card(self):
        """Test that auth_required returns proper card response."""
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=False,
        )

        # Find and call the auth_required function
        auth_func = None
        for func in toolkit.functions.values():
            if func.name == "contacts_auth_required":
                auth_func = func
                break

        self.assertIsNotNone(auth_func)
        assert auth_func is not None  # for mypy
        result = auth_func.entrypoint()  # type: ignore[misc]

        self.assertIn("card", result)
        self.assertEqual(result["card"], "contacts-auth-required")


class TestContactsToolkitErrorCard(unittest.TestCase):
    """Tests for error_card functionality."""

    def test_error_card_returns_error_response(self):
        """Test that error_card returns proper error response."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Call error_card method directly (it's a method on BaseToolkit, not a registered tool)
        result = toolkit.error_card(message="Test error message")

        self.assertIn("card", result)
        self.assertEqual(result["card"], "error")
        self.assertIn("message", result)


class TestContactsAuthError(unittest.TestCase):
    """Tests for ContactsAuthError exception."""

    def test_contacts_auth_error_is_runtime_error(self):
        """Test that ContactsAuthError is a RuntimeError subclass."""
        error = ContactsAuthError("Test error")
        self.assertIsInstance(error, RuntimeError)

    def test_contacts_auth_error_message(self):
        """Test that ContactsAuthError stores message correctly."""
        error = ContactsAuthError("Authentication failed")
        self.assertEqual(str(error), "Authentication failed")


class TestContactsToolkitStr(unittest.TestCase):
    """Tests for ContactsToolkit string representation."""

    def test_str_authenticated(self):
        """Test string representation for authenticated toolkit."""
        fetch_token = MagicMock(return_value="test_token")
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=True,
            fetch_token_func=fetch_token,
        )

        str_repr = str(toolkit)
        self.assertIn("ContactsToolkit", str_repr)
        self.assertIn("google_contacts", str_repr)
        self.assertIn("auth=True", str_repr)

    def test_str_unauthenticated(self):
        """Test string representation for unauthenticated toolkit."""
        toolkit = ContactsToolkit(
            user_id="user123",
            service_name="google_contacts",
            auth=False,
        )

        str_repr = str(toolkit)
        self.assertIn("auth=False", str_repr)


if __name__ == "__main__":
    unittest.main()
