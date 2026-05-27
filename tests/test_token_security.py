import os
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict

from api.services.token_security import TokenEncryption, TokenSecurityError, TokenValidator, get_token_encryption


class TestTokenEncryption(unittest.TestCase):
    """Test token encryption and decryption."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a test encryption key
        self.test_key = "test_key_for_unit_tests"
        self.encryption = TokenEncryption(self.test_key)

    def test_encrypt_decrypt_oauth2_token(self):
        """Test encryption and decryption of OAuth2 token data."""
        token_data = {
            "access_token": "ya29.test_access_token",
            "refresh_token": "1//test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/drive",
        }

        # Encrypt
        encrypted = self.encryption.encrypt_token_data(token_data)
        self.assertIsInstance(encrypted, str)
        self.assertNotIn("ya29.test_access_token", encrypted)

        # Decrypt
        decrypted = self.encryption.decrypt_token_data(encrypted)
        self.assertEqual(decrypted, token_data)

    def test_encrypt_decrypt_api_key_token(self):
        """Test encryption and decryption of API key token data."""
        token_data = {"api_key": "sk-test_api_key_123", "organization_id": "org-123456"}

        # Encrypt
        encrypted = self.encryption.encrypt_token_data(token_data)
        self.assertIsInstance(encrypted, str)
        self.assertNotIn("sk-test_api_key_123", encrypted)

        # Decrypt
        decrypted = self.encryption.decrypt_token_data(encrypted)
        self.assertEqual(decrypted, token_data)

    def test_encrypt_decrypt_jwt_token(self):
        """Test encryption and decryption of JWT token data."""
        token_data = {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
            "algorithm": "HS256",
            "issuer": "test-issuer",
        }

        # Encrypt
        encrypted = self.encryption.encrypt_token_data(token_data)
        self.assertIsInstance(encrypted, str)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test", encrypted)

        # Decrypt
        decrypted = self.encryption.decrypt_token_data(encrypted)
        self.assertEqual(decrypted, token_data)

    def test_encrypt_empty_data(self):
        """Test encryption of empty data."""
        token_data: Dict[str, Any] = {}

        # Should not raise an error
        encrypted = self.encryption.encrypt_token_data(token_data)
        decrypted = self.encryption.decrypt_token_data(encrypted)
        self.assertEqual(decrypted, token_data)

    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data."""
        with self.assertRaises(TokenSecurityError):
            self.encryption.decrypt_token_data("invalid_encrypted_data")

    def test_encrypt_with_datetime(self):
        """Test encryption of data containing datetime objects."""
        token_data = {"access_token": "test_token", "created_at": datetime.utcnow()}

        # Should handle datetime serialization
        encrypted = self.encryption.encrypt_token_data(token_data)
        decrypted = self.encryption.decrypt_token_data(encrypted)

        # Datetime should be converted to string
        self.assertIsInstance(decrypted["created_at"], str)
        self.assertEqual(decrypted["access_token"], "test_token")


class TestTokenValidator(unittest.TestCase):
    """Test token validation utilities."""

    def test_is_token_expired(self):
        """Test token expiration checking."""
        # Token expires in 1 hour
        expires_at = datetime.utcnow() + timedelta(hours=1)
        self.assertFalse(TokenValidator.is_token_expired(expires_at))

        # Token expires in 30 seconds (within buffer)
        expires_at = datetime.utcnow() + timedelta(seconds=30)
        self.assertTrue(TokenValidator.is_token_expired(expires_at, buffer_seconds=60))

        # Token expired 1 hour ago
        expires_at = datetime.utcnow() - timedelta(hours=1)
        self.assertTrue(TokenValidator.is_token_expired(expires_at))

        # Token never expires
        self.assertFalse(TokenValidator.is_token_expired(None))

    def test_validate_token_type(self):
        """Test token type validation."""
        # Valid token types
        self.assertTrue(TokenValidator.validate_token_type("oauth2"))
        self.assertTrue(TokenValidator.validate_token_type("api_key"))
        self.assertTrue(TokenValidator.validate_token_type("jwt"))
        self.assertTrue(TokenValidator.validate_token_type("OAUTH2"))  # Case insensitive

        # Invalid token types
        self.assertFalse(TokenValidator.validate_token_type("invalid"))
        self.assertFalse(TokenValidator.validate_token_type(""))
        self.assertFalse(TokenValidator.validate_token_type("bearer"))

    def test_validate_provider(self):
        """Test provider validation."""
        # Valid providers
        self.assertTrue(TokenValidator.validate_provider("google"))
        self.assertTrue(TokenValidator.validate_provider("openai"))
        self.assertTrue(TokenValidator.validate_provider("slack"))
        self.assertTrue(TokenValidator.validate_provider("GOOGLE"))  # Case insensitive

        # Invalid providers
        self.assertFalse(TokenValidator.validate_provider("invalid_provider"))
        self.assertFalse(TokenValidator.validate_provider(""))

    def test_validate_oauth2_token_data(self):
        """Test OAuth2 token data validation."""
        # Valid OAuth2 data
        valid_data = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        self.assertTrue(TokenValidator.validate_oauth2_token_data(valid_data))

        # Minimal valid data
        minimal_data = {"access_token": "test_token"}
        self.assertTrue(TokenValidator.validate_oauth2_token_data(minimal_data))

        # Missing required field
        invalid_data = {"refresh_token": "test_refresh"}
        self.assertFalse(TokenValidator.validate_oauth2_token_data(invalid_data))

        # Unknown field
        unknown_field_data = {"access_token": "test_token", "unknown_field": "value"}
        self.assertFalse(TokenValidator.validate_oauth2_token_data(unknown_field_data))

    def test_validate_api_key_token_data(self):
        """Test API key token data validation."""
        # Valid API key data
        valid_data = {"api_key": "sk-test123", "api_secret": "secret123", "organization_id": "org-123"}
        self.assertTrue(TokenValidator.validate_api_key_token_data(valid_data))

        # Minimal valid data
        minimal_data = {"api_key": "sk-test123"}
        self.assertTrue(TokenValidator.validate_api_key_token_data(minimal_data))

        # Missing required field
        invalid_data = {"api_secret": "secret123"}
        self.assertFalse(TokenValidator.validate_api_key_token_data(invalid_data))

    def test_validate_jwt_token_data(self):
        """Test JWT token data validation."""
        # Valid JWT data
        valid_data = {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
            "algorithm": "HS256",
            "issuer": "test-issuer",
        }
        self.assertTrue(TokenValidator.validate_jwt_token_data(valid_data))

        # Minimal valid data
        minimal_data = {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"}
        self.assertTrue(TokenValidator.validate_jwt_token_data(minimal_data))

        # Missing required field
        invalid_data = {"algorithm": "HS256"}
        self.assertFalse(TokenValidator.validate_jwt_token_data(invalid_data))

    def test_validate_token_data_structure(self):
        """Test complete token data structure validation."""
        # OAuth2
        oauth2_data = {"access_token": "test"}
        self.assertTrue(TokenValidator.validate_token_data_structure("oauth2", oauth2_data))

        # API Key
        api_key_data = {"api_key": "test"}
        self.assertTrue(TokenValidator.validate_token_data_structure("api_key", api_key_data))

        # JWT
        jwt_data = {"token": "test"}
        self.assertTrue(TokenValidator.validate_token_data_structure("jwt", jwt_data))

        # Invalid token type
        self.assertFalse(TokenValidator.validate_token_data_structure("invalid", {}))


class TestGlobalEncryption(unittest.TestCase):
    """Test global encryption instance."""

    def test_get_token_encryption(self):
        """Test getting global encryption instance."""
        # Set environment variable for this test
        test_key = "dGVzdF9rZXlfZm9yX3VuaXRfdGVzdHM="  # base64 encoded test key
        original_key = os.environ.get("SECRET_TOKEN_ENC_KEY")
        os.environ["SECRET_TOKEN_ENC_KEY"] = test_key

        try:
            # Reset global instance to None to test fresh initialization
            import api.services.token_security as token_security_module

            token_security_module._encryption_instance = None

            # Should return the same instance
            enc1 = get_token_encryption()
            enc2 = get_token_encryption()
            self.assertIs(enc1, enc2)
        finally:
            # Clean up global instance
            import api.services.token_security as token_security_module

            token_security_module._encryption_instance = None

            # Restore original key
            if original_key:
                os.environ["SECRET_TOKEN_ENC_KEY"] = original_key
            else:
                os.environ.pop("SECRET_TOKEN_ENC_KEY", None)

    def test_encryption_with_env_var(self):
        """Test encryption initialization with environment variable."""
        # Set environment variable
        test_key = "dGVzdF9rZXlfZm9yX3VuaXRfdGVzdHM="  # base64 encoded test key
        os.environ["SECRET_TOKEN_ENC_KEY"] = test_key

        try:
            # Create new encryption instance
            encryption = TokenEncryption()

            # Test that it works
            test_data = {"test": "data"}
            encrypted = encryption.encrypt_token_data(test_data)
            decrypted = encryption.decrypt_token_data(encrypted)
            self.assertEqual(decrypted, test_data)

        finally:
            # Clean up
            if "SECRET_TOKEN_ENC_KEY" in os.environ:
                del os.environ["SECRET_TOKEN_ENC_KEY"]

    def test_missing_encryption_key_raises_exception(self):
        """Test that missing SECRET_TOKEN_ENC_KEY raises an exception."""
        # Store original key if it exists
        original_key = os.environ.pop("SECRET_TOKEN_ENC_KEY", None)

        try:
            with self.assertRaises(TokenSecurityError) as context:
                TokenEncryption()

            # Verify the error message contains the required information
            error_message = str(context.exception)
            self.assertIn("SECRET_TOKEN_ENC_KEY environment variable is required", error_message)
            self.assertIn("Generate a key using", error_message)
            self.assertIn("Fernet.generate_key", error_message)

        finally:
            # Restore original key if it existed
            if original_key:
                os.environ["SECRET_TOKEN_ENC_KEY"] = original_key


if __name__ == "__main__":
    unittest.main()
