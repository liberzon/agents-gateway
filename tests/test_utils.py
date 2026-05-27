"""
Utilities for testing that provide common mocking functionality.
"""

import os
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import create_app
from db.session import get_db


def create_test_client():
    """
    Create a test client with mocked dependencies.
    This avoids database connection issues in tests.
    """
    # Disable authentication for tests
    os.environ["AUTH_DISABLED"] = "true"

    app = create_app()

    # Mock database dependency to avoid real database connections
    def mock_get_db():
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = None  # Simulate successful DB query
        yield mock_db

    app.dependency_overrides[get_db] = mock_get_db

    return TestClient(app), app


class BaseTestCase:
    """
    Base test class that sets up mocked dependencies.
    Can be mixed with unittest.TestCase.
    """

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.client, self.app = create_test_client()
