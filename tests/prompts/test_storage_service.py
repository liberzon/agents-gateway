import unittest
from unittest.mock import MagicMock, patch

from api.services.models import PullPromptResponse, ToolSchema
from prompts.storage.service import PromptsServiceStorage


class TestPromptsServiceStorage(unittest.TestCase):
    """Tests for PromptsServiceStorage backend."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("prompts.storage.service.PromptsServiceClient"):
            self.storage = PromptsServiceStorage()
            self.mock_client: MagicMock = self.storage.client  # type: ignore[assignment]

        # Create a mock PullPromptResponse
        self.mock_response = MagicMock(spec=PullPromptResponse)
        self.mock_response.name = "test-prompt"
        self.mock_response.template = "You are a helpful assistant."
        self.mock_response.description = "A test prompt"
        self.mock_response.tags = ["test", "example"]
        self.mock_response.tools = [ToolSchema(name="tool1", description="A tool", parameters={"type": "object"})]

    def test_init(self):
        """Test initialization creates a client."""
        with patch("prompts.storage.service.PromptsServiceClient") as mock_client_class:
            storage = PromptsServiceStorage()
            mock_client_class.assert_called_once()
            self.assertIsNotNone(storage.client)

    def test_to_prompt_data_basic(self):
        """Test converting PullPromptResponse to PromptData."""
        prompt_data = self.storage._to_prompt_data("test-prompt", self.mock_response)

        self.assertEqual(prompt_data.id, "test-prompt")
        self.assertEqual(prompt_data.name, "test-prompt")
        self.assertEqual(prompt_data.template, "You are a helpful assistant.")
        self.assertEqual(prompt_data.description, "A test prompt")
        self.assertEqual(prompt_data.tags, ["test", "example"])
        self.assertEqual(len(prompt_data.tools), 1)
        self.assertEqual(prompt_data.tools[0]["name"], "tool1")
        self.assertEqual(prompt_data.version, 1)
        self.assertTrue(prompt_data.is_active)
        self.assertIsNone(prompt_data.created_at)
        self.assertIsNone(prompt_data.updated_at)

    def test_to_prompt_data_empty_tags(self):
        """Test conversion with empty tags."""
        self.mock_response.tags = None
        prompt_data = self.storage._to_prompt_data("test-prompt", self.mock_response)
        self.assertEqual(prompt_data.tags, [])

    def test_to_prompt_data_empty_tools(self):
        """Test conversion with empty tools."""
        self.mock_response.tools = None
        prompt_data = self.storage._to_prompt_data("test-prompt", self.mock_response)
        self.assertEqual(prompt_data.tools, [])

    def test_to_prompt_data_dict_tools(self):
        """Test conversion with dict tools (instead of ToolSchema)."""
        self.mock_response.tools = [{"name": "tool1", "description": "A tool", "parameters": {}}]
        prompt_data = self.storage._to_prompt_data("test-prompt", self.mock_response)
        self.assertEqual(len(prompt_data.tools), 1)
        self.assertEqual(prompt_data.tools[0]["name"], "tool1")

    def test_to_push_request_basic(self):
        """Test creating a PushPromptRequest."""
        request = self.storage._to_push_request(
            name="test-prompt",
            template="You are helpful.",
            description="A prompt",
            tags=["test"],
            tools=[{"name": "tool1", "description": "desc", "parameters": {}}],
        )

        self.assertEqual(request.name, "test-prompt")
        self.assertEqual(request.raw_template, "You are helpful.")
        self.assertEqual(request.description, "A prompt")
        self.assertEqual(request.tags, ["test"])
        self.assertIsNotNone(request.tools)
        assert request.tools is not None
        self.assertEqual(len(request.tools), 1)
        self.assertEqual(request.tools[0].name, "tool1")

    def test_to_push_request_no_tools(self):
        """Test creating a PushPromptRequest without tools."""
        request = self.storage._to_push_request(
            name="test-prompt",
            template="You are helpful.",
        )

        self.assertEqual(request.name, "test-prompt")
        self.assertIsNone(request.tools)

    def test_get_found(self):
        """Test getting an existing prompt."""
        self.mock_client.get_prompt.return_value = self.mock_response

        result = self.storage.get("test-prompt")

        self.mock_client.get_prompt.assert_called_once_with("test-prompt")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.id, "test-prompt")
        self.assertEqual(result.template, "You are a helpful assistant.")

    def test_get_not_found(self):
        """Test getting a non-existent prompt."""
        self.mock_client.get_prompt.return_value = None

        result = self.storage.get("nonexistent")

        self.assertIsNone(result)

    def test_get_all(self):
        """Test getting all prompts."""
        mock_response_2 = MagicMock(spec=PullPromptResponse)
        mock_response_2.name = "prompt-2"
        mock_response_2.template = "Another template."
        mock_response_2.description = None
        mock_response_2.tags = None
        mock_response_2.tools = None

        self.mock_client.list_prompts.return_value = ["test-prompt", "prompt-2"]
        self.mock_client.get_prompt.side_effect = [self.mock_response, mock_response_2]

        result = self.storage.get_all()

        self.mock_client.list_prompts.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "test-prompt")
        self.assertEqual(result[1].id, "prompt-2")

    def test_get_all_empty(self):
        """Test getting all prompts when none exist."""
        self.mock_client.list_prompts.return_value = []

        result = self.storage.get_all()

        self.assertEqual(len(result), 0)

    def test_get_all_partial_failure(self):
        """Test getting all prompts when some fetches fail."""
        self.mock_client.list_prompts.return_value = ["test-prompt", "nonexistent"]
        self.mock_client.get_prompt.side_effect = [self.mock_response, None]

        result = self.storage.get_all()

        # Only successful fetches should be included
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "test-prompt")

    def test_create_success(self):
        """Test creating a prompt."""
        self.mock_client.create_prompt.return_value = True
        self.mock_client.get_prompt.return_value = self.mock_response

        result = self.storage.create(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags=["test"],
            tools=[{"name": "tool1", "description": "desc", "parameters": {}}],
        )

        self.mock_client.create_prompt.assert_called_once()
        self.assertEqual(result.id, "test-prompt")
        self.assertEqual(result.name, "Test Prompt")  # Name override

    def test_create_failure(self):
        """Test creating a prompt when service fails."""
        self.mock_client.create_prompt.return_value = False

        with self.assertRaises(RuntimeError) as context:
            self.storage.create(
                prompt_id="test-prompt",
                name="Test Prompt",
                template="You are helpful.",
            )

        self.assertIn("Failed to create prompt", str(context.exception))

    def test_create_success_fetch_fails(self):
        """Test creating a prompt when create succeeds but fetch fails."""
        self.mock_client.create_prompt.return_value = True
        self.mock_client.get_prompt.return_value = None

        result = self.storage.create(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are helpful.",
            description="A prompt",
            tags=["test"],
        )

        # Should return what we know
        self.assertEqual(result.id, "test-prompt")
        self.assertEqual(result.name, "Test Prompt")
        self.assertEqual(result.template, "You are helpful.")

    def test_update_success(self):
        """Test updating an existing prompt."""
        # First get returns existing prompt
        existing_response = MagicMock(spec=PullPromptResponse)
        existing_response.name = "test-prompt"
        existing_response.template = "Old template."
        existing_response.description = "Old description"
        existing_response.tags = ["old"]
        existing_response.tools = None

        # After update, get returns updated prompt
        updated_response = MagicMock(spec=PullPromptResponse)
        updated_response.name = "test-prompt"
        updated_response.template = "New template."
        updated_response.description = "Old description"
        updated_response.tags = ["old"]
        updated_response.tools = None

        self.mock_client.get_prompt.side_effect = [existing_response, updated_response]
        self.mock_client.create_prompt.return_value = True

        result = self.storage.update(
            prompt_id="test-prompt",
            template="New template.",
        )

        self.mock_client.create_prompt.assert_called_once()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template, "New template.")

    def test_update_not_found(self):
        """Test updating a non-existent prompt."""
        self.mock_client.get_prompt.return_value = None

        result = self.storage.update(prompt_id="nonexistent", name="New Name")

        self.assertIsNone(result)
        self.mock_client.create_prompt.assert_not_called()

    def test_update_failure(self):
        """Test updating when service fails."""
        existing_response = MagicMock(spec=PullPromptResponse)
        existing_response.name = "test-prompt"
        existing_response.template = "Old template."
        existing_response.description = None
        existing_response.tags = None
        existing_response.tools = None

        self.mock_client.get_prompt.return_value = existing_response
        self.mock_client.create_prompt.return_value = False

        result = self.storage.update(
            prompt_id="test-prompt",
            template="New template.",
        )

        self.assertIsNone(result)

    def test_delete_success(self):
        """Test deleting a prompt."""
        self.mock_client.delete_prompt.return_value = True

        result = self.storage.delete("test-prompt")

        self.mock_client.delete_prompt.assert_called_once_with("test-prompt")
        self.assertTrue(result)

    def test_delete_not_found(self):
        """Test deleting a non-existent prompt."""
        self.mock_client.delete_prompt.return_value = False

        result = self.storage.delete("nonexistent")

        self.assertFalse(result)

    def test_exists_true(self):
        """Test checking if a prompt exists."""
        self.mock_client.get_prompt.return_value = self.mock_response

        result = self.storage.exists("test-prompt")

        self.mock_client.get_prompt.assert_called_once_with("test-prompt")
        self.assertTrue(result)

    def test_exists_false(self):
        """Test checking if a non-existent prompt exists."""
        self.mock_client.get_prompt.return_value = None

        result = self.storage.exists("nonexistent")

        self.assertFalse(result)


class TestGetPromptStorageFactory(unittest.TestCase):
    """Tests for the get_prompt_storage factory function with service backend."""

    @patch.dict("os.environ", {"PROMPT_STORAGE_BACKEND": "service"})
    @patch("prompts.storage.service.PromptsServiceClient")
    def test_get_service_storage(self, mock_client_class):
        """Test getting service storage backend."""
        from prompts.storage import get_prompt_storage

        storage = get_prompt_storage()

        self.assertIsInstance(storage, PromptsServiceStorage)


if __name__ == "__main__":
    unittest.main()
