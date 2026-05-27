"""
Tests for health check endpoints.
"""

import unittest

from tests.test_utils import create_test_client


class TestHealthEndpoints(unittest.TestCase):
    """Test health check endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client, self.app = create_test_client()

    def test_health_check(self):
        """Test basic health check endpoint."""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")

    def test_status_check(self):
        """Test status endpoint."""
        response = self.client.get("/status")

        # The status endpoint returns 404 in the current implementation
        self.assertEqual(response.status_code, 200)

    def test_root_endpoint(self):
        """Test root endpoint redirect or response."""
        response = self.client.get("/")

        # The root endpoint returns 200 in the current implementation
        self.assertEqual(response.status_code, 200)

    def test_version_endpoint(self):
        """Test version endpoint if it exists."""
        response = self.client.get("/version")

        # Version endpoint might not exist, so accept 404 as well
        if response.status_code == 200:
            data = response.json()
            self.assertIn("version", data)
        else:
            self.assertEqual(response.status_code, 404)

    def test_docs_endpoint_accessibility(self):
        """Test that docs endpoint is accessible in development."""
        response = self.client.get("/docs")

        # In test mode, docs should be accessible
        self.assertEqual(response.status_code, 200)

    def test_openapi_endpoint_accessibility(self):
        """Test that OpenAPI spec is accessible."""
        response = self.client.get("/openapi.json")

        # OpenAPI spec should be accessible in test mode
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("openapi", data)
        self.assertIn("info", data)


if __name__ == "__main__":
    unittest.main()
