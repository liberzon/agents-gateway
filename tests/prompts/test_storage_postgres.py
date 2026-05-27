import datetime
import unittest
from unittest.mock import MagicMock, patch

from db.db_models import PromptDB
from prompts.storage.postgres import PostgresStorage


class TestPostgresStorage(unittest.TestCase):
    """Tests for PostgresStorage backend."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.storage = PostgresStorage(self.mock_db)

        # Create a mock PromptDB instance
        self.mock_prompt_db = MagicMock(spec=PromptDB)
        self.mock_prompt_db.id = "test-prompt"
        self.mock_prompt_db.name = "Test Prompt"
        self.mock_prompt_db.template = "You are a helpful assistant."
        self.mock_prompt_db.description = "A test prompt"
        self.mock_prompt_db.tags = '["test", "example"]'
        self.mock_prompt_db.tools = '[{"name": "tool1"}]'
        self.mock_prompt_db.version = 1
        self.mock_prompt_db.created_at = datetime.datetime(2025, 1, 1, 12, 0, 0)
        self.mock_prompt_db.updated_at = datetime.datetime(2025, 1, 1, 12, 0, 0)
        self.mock_prompt_db.is_active = True

    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.storage.db, self.mock_db)

    def test_to_prompt_data_basic(self):
        """Test converting PromptDB to PromptData."""
        prompt_data = self.storage._to_prompt_data(self.mock_prompt_db)

        self.assertEqual(prompt_data.id, "test-prompt")
        self.assertEqual(prompt_data.name, "Test Prompt")
        self.assertEqual(prompt_data.template, "You are a helpful assistant.")
        self.assertEqual(prompt_data.description, "A test prompt")
        self.assertEqual(prompt_data.tags, ["test", "example"])
        self.assertEqual(prompt_data.tools, [{"name": "tool1"}])
        self.assertEqual(prompt_data.version, 1)
        self.assertTrue(prompt_data.is_active)

    def test_to_prompt_data_empty_tags(self):
        """Test conversion with empty tags."""
        self.mock_prompt_db.tags = None
        prompt_data = self.storage._to_prompt_data(self.mock_prompt_db)
        self.assertEqual(prompt_data.tags, [])

    def test_to_prompt_data_invalid_tags_json(self):
        """Test conversion with invalid JSON tags."""
        self.mock_prompt_db.tags = "not valid json"
        prompt_data = self.storage._to_prompt_data(self.mock_prompt_db)
        self.assertEqual(prompt_data.tags, [])

    def test_to_prompt_data_empty_tools(self):
        """Test conversion with empty tools."""
        self.mock_prompt_db.tools = None
        prompt_data = self.storage._to_prompt_data(self.mock_prompt_db)
        self.assertEqual(prompt_data.tools, [])

    def test_to_prompt_data_invalid_tools_json(self):
        """Test conversion with invalid JSON tools."""
        self.mock_prompt_db.tools = "not valid json"
        prompt_data = self.storage._to_prompt_data(self.mock_prompt_db)
        self.assertEqual(prompt_data.tools, [])

    @patch("prompts.storage.postgres.db_create_prompt")
    def test_create(self, mock_create):
        """Test creating a prompt."""
        mock_create.return_value = self.mock_prompt_db

        result = self.storage.create(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags=["test"],
            tools=[{"name": "tool1"}],
        )

        mock_create.assert_called_once_with(
            db=self.mock_db,
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags=["test"],
            tools=[{"name": "tool1"}],
        )
        self.assertEqual(result.id, "test-prompt")

    @patch("prompts.storage.postgres.db_get_prompt")
    def test_get_found(self, mock_get):
        """Test getting an existing prompt."""
        mock_get.return_value = self.mock_prompt_db

        result = self.storage.get("test-prompt")

        mock_get.assert_called_once_with(self.mock_db, "test-prompt")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.id, "test-prompt")

    @patch("prompts.storage.postgres.db_get_prompt")
    def test_get_not_found(self, mock_get):
        """Test getting a non-existent prompt."""
        mock_get.return_value = None

        result = self.storage.get("nonexistent")

        self.assertIsNone(result)

    @patch("prompts.storage.postgres.db_get_all_prompts")
    def test_get_all(self, mock_get_all):
        """Test getting all prompts."""
        mock_prompt_2 = MagicMock(spec=PromptDB)
        mock_prompt_2.id = "prompt-2"
        mock_prompt_2.name = "Prompt 2"
        mock_prompt_2.template = "Another template."
        mock_prompt_2.description = None
        mock_prompt_2.tags = None
        mock_prompt_2.tools = None
        mock_prompt_2.version = 1
        mock_prompt_2.created_at = None
        mock_prompt_2.updated_at = None
        mock_prompt_2.is_active = True

        mock_get_all.return_value = [self.mock_prompt_db, mock_prompt_2]

        result = self.storage.get_all()

        mock_get_all.assert_called_once_with(self.mock_db)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "test-prompt")
        self.assertEqual(result[1].id, "prompt-2")

    @patch("prompts.storage.postgres.db_update_prompt")
    def test_update_found(self, mock_update):
        """Test updating an existing prompt."""
        updated_prompt = MagicMock(spec=PromptDB)
        updated_prompt.id = "test-prompt"
        updated_prompt.name = "Updated Name"
        updated_prompt.template = "Updated template."
        updated_prompt.description = "Updated description"
        updated_prompt.tags = '["updated"]'
        updated_prompt.tools = None
        updated_prompt.version = 2
        updated_prompt.created_at = datetime.datetime(2025, 1, 1, 12, 0, 0)
        updated_prompt.updated_at = datetime.datetime(2025, 1, 2, 12, 0, 0)
        updated_prompt.is_active = True

        mock_update.return_value = updated_prompt

        result = self.storage.update(
            prompt_id="test-prompt",
            name="Updated Name",
            template="Updated template.",
        )

        mock_update.assert_called_once()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "Updated Name")
        self.assertEqual(result.version, 2)

    @patch("prompts.storage.postgres.db_update_prompt")
    def test_update_not_found(self, mock_update):
        """Test updating a non-existent prompt."""
        mock_update.return_value = None

        result = self.storage.update(prompt_id="nonexistent", name="New Name")

        self.assertIsNone(result)

    @patch("prompts.storage.postgres.db_soft_delete_prompt")
    def test_delete(self, mock_soft_delete):
        """Test soft deleting a prompt."""
        mock_soft_delete.return_value = True

        result = self.storage.delete("test-prompt")

        mock_soft_delete.assert_called_once_with(self.mock_db, "test-prompt")
        self.assertTrue(result)

    @patch("prompts.storage.postgres.db_soft_delete_prompt")
    def test_delete_not_found(self, mock_soft_delete):
        """Test soft deleting a non-existent prompt."""
        mock_soft_delete.return_value = False

        result = self.storage.delete("nonexistent")

        self.assertFalse(result)

    @patch("prompts.storage.postgres.db_delete_prompt")
    def test_hard_delete(self, mock_delete):
        """Test hard deleting a prompt."""
        mock_delete.return_value = True

        result = self.storage.hard_delete("test-prompt")

        mock_delete.assert_called_once_with(self.mock_db, "test-prompt")
        self.assertTrue(result)

    @patch("prompts.storage.postgres.db_delete_prompt")
    def test_hard_delete_not_found(self, mock_delete):
        """Test hard deleting a non-existent prompt."""
        mock_delete.return_value = False

        result = self.storage.hard_delete("nonexistent")

        self.assertFalse(result)

    @patch("prompts.storage.postgres.db_prompt_exists")
    def test_exists_true(self, mock_exists):
        """Test checking if a prompt exists."""
        mock_exists.return_value = True

        result = self.storage.exists("test-prompt")

        mock_exists.assert_called_once_with(self.mock_db, "test-prompt")
        self.assertTrue(result)

    @patch("prompts.storage.postgres.db_prompt_exists")
    def test_exists_false(self, mock_exists):
        """Test checking if a non-existent prompt exists."""
        mock_exists.return_value = False

        result = self.storage.exists("nonexistent")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
