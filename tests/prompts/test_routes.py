import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from prompts.models import PromptData
from tests.test_utils import create_test_client


class MockStorage:
    """Mock storage backend for testing."""

    def __init__(self):
        self.prompts: dict[str, PromptData] = {}

    def create(self, prompt_id, name, template, description=None, tags=None, tools=None):
        prompt = PromptData(
            id=prompt_id,
            name=name,
            template=template,
            description=description,
            tags=tags or [],
            tools=tools or [],
            version=1,
        )
        self.prompts[prompt_id] = prompt
        return prompt

    def get(self, prompt_id):
        return self.prompts.get(prompt_id)

    def get_all(self):
        return list(self.prompts.values())

    def update(self, prompt_id, **kwargs):
        if prompt_id not in self.prompts:
            return None
        prompt = self.prompts[prompt_id]
        for key, value in kwargs.items():
            if value is not None:
                setattr(prompt, key, value)
        prompt.version += 1
        return prompt

    def delete(self, prompt_id):
        if prompt_id in self.prompts:
            del self.prompts[prompt_id]
            return True
        return False

    def exists(self, prompt_id):
        return prompt_id in self.prompts


class TestPromptsRoutes(unittest.TestCase):
    """Tests for prompts API routes."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        self.mock_storage = MockStorage()
        self.client, self.app = create_test_client()

        # Manually register the v2 router (including prompts)
        from api.routes.v2_router import get_v2_router

        self.app.include_router(get_v2_router())

        # Recreate client with the updated app
        self.client = TestClient(self.app)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_create_prompt(self, mock_get_storage):
        """Test creating a prompt via API."""
        mock_get_storage.return_value = self.mock_storage

        response = self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Test Prompt",
                "template": "You are a helpful assistant.",
                "description": "A test prompt",
                "tags": ["test"],
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "test-prompt")
        self.assertEqual(data["name"], "Test Prompt")

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_create_prompt_duplicate(self, mock_get_storage):
        """Test creating a duplicate prompt."""
        mock_get_storage.return_value = self.mock_storage

        # Create first prompt
        self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Test Prompt",
                "template": "You are a helpful assistant.",
            },
        )

        # Try to create duplicate
        response = self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Duplicate",
                "template": "Another template here.",
            },
        )

        self.assertEqual(response.status_code, 409)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_list_prompts(self, mock_get_storage):
        """Test listing all prompts."""
        mock_get_storage.return_value = self.mock_storage

        # Create some prompts
        self.client.post(
            "/v2/prompts",
            json={
                "id": "prompt-1",
                "name": "Prompt 1",
                "template": "Template one content here.",
            },
        )
        self.client.post(
            "/v2/prompts",
            json={
                "id": "prompt-2",
                "name": "Prompt 2",
                "template": "Template two content here.",
            },
        )

        response = self.client.get("/v2/prompts")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["prompts"]), 2)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_get_prompt(self, mock_get_storage):
        """Test getting a specific prompt."""
        mock_get_storage.return_value = self.mock_storage

        # Create a prompt
        self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Test Prompt",
                "template": "You are a helpful assistant.",
            },
        )

        response = self.client.get("/v2/prompts/test-prompt")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "test-prompt")
        self.assertEqual(data["name"], "Test Prompt")

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_get_prompt_not_found(self, mock_get_storage):
        """Test getting a non-existent prompt."""
        mock_get_storage.return_value = self.mock_storage

        response = self.client.get("/v2/prompts/nonexistent")

        self.assertEqual(response.status_code, 404)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_update_prompt(self, mock_get_storage):
        """Test updating a prompt."""
        mock_get_storage.return_value = self.mock_storage

        # Create a prompt
        self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Original Name",
                "template": "You are a helpful assistant.",
            },
        )

        response = self.client.put(
            "/v2/prompts/test-prompt",
            json={"name": "Updated Name"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Updated Name")
        self.assertEqual(data["version"], 2)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_update_prompt_not_found(self, mock_get_storage):
        """Test updating a non-existent prompt."""
        mock_get_storage.return_value = self.mock_storage

        response = self.client.put(
            "/v2/prompts/nonexistent",
            json={"name": "New Name"},
        )

        self.assertEqual(response.status_code, 404)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_delete_prompt(self, mock_get_storage):
        """Test deleting a prompt."""
        mock_get_storage.return_value = self.mock_storage

        # Create a prompt
        self.client.post(
            "/v2/prompts",
            json={
                "id": "test-prompt",
                "name": "Test Prompt",
                "template": "You are a helpful assistant.",
            },
        )

        response = self.client.delete("/v2/prompts/test-prompt")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Prompt deleted successfully")

        # Verify it's gone
        response = self.client.get("/v2/prompts/test-prompt")
        self.assertEqual(response.status_code, 404)

    @patch("api.routes.v2.prompts.get_prompt_storage")
    def test_delete_prompt_not_found(self, mock_get_storage):
        """Test deleting a non-existent prompt."""
        mock_get_storage.return_value = self.mock_storage

        response = self.client.delete("/v2/prompts/nonexistent")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
