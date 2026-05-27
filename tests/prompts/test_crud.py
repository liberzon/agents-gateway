import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from db.db_models import PromptDB
from db.prompt_crud import (
    create_prompt,
    delete_prompt,
    get_all_prompts,
    get_prompt,
    prompt_exists,
    reactivate_prompt,
    soft_delete_prompt,
    update_prompt,
)


class TestPromptCRUD(unittest.TestCase):
    """Tests for prompt CRUD operations."""

    def setUp(self):
        """Set up mock database session."""
        self.mock_db = MagicMock()
        self.mock_prompt = PromptDB(
            id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags='["test"]',
            tools=None,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

    def test_create_prompt(self):
        """Test creating a new prompt."""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        result = create_prompt(
            db=self.mock_db,
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags=["test"],
        )

        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.assertEqual(result.id, "test-prompt")
        self.assertEqual(result.name, "Test Prompt")

    def test_get_prompt(self):
        """Test getting a prompt by ID."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_prompt

        result = get_prompt(self.mock_db, "test-prompt")

        self.assertIsNotNone(result)
        assert result is not None  # for mypy
        self.assertEqual(result.id, "test-prompt")

    def test_get_prompt_not_found(self):
        """Test getting a non-existent prompt."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_prompt(self.mock_db, "nonexistent")

        self.assertIsNone(result)

    def test_get_all_prompts(self):
        """Test getting all prompts."""
        mock_prompts = [self.mock_prompt]
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_prompts

        result = get_all_prompts(self.mock_db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "test-prompt")

    def test_update_prompt(self):
        """Test updating a prompt."""
        # Mock get_prompt to return our mock
        with patch("db.prompt_crud.get_prompt", return_value=self.mock_prompt):
            self.mock_db.commit = MagicMock()
            self.mock_db.refresh = MagicMock()

            result = update_prompt(
                db=self.mock_db,
                prompt_id="test-prompt",
                name="Updated Name",
            )

            self.assertIsNotNone(result)
            self.mock_db.commit.assert_called_once()

    def test_update_prompt_not_found(self):
        """Test updating a non-existent prompt."""
        with patch("db.prompt_crud.get_prompt", return_value=None):
            result = update_prompt(
                db=self.mock_db,
                prompt_id="nonexistent",
                name="New Name",
            )

            self.assertIsNone(result)

    def test_soft_delete_prompt(self):
        """Test soft deleting a prompt."""
        with patch("db.prompt_crud.get_prompt", return_value=self.mock_prompt):
            self.mock_db.commit = MagicMock()

            result = soft_delete_prompt(self.mock_db, "test-prompt")

            self.assertTrue(result)
            self.mock_db.commit.assert_called_once()

    def test_soft_delete_prompt_not_found(self):
        """Test soft deleting a non-existent prompt."""
        with patch("db.prompt_crud.get_prompt", return_value=None):
            result = soft_delete_prompt(self.mock_db, "nonexistent")

            self.assertFalse(result)

    def test_delete_prompt(self):
        """Test hard deleting a prompt."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_prompt
        self.mock_db.delete = MagicMock()
        self.mock_db.commit = MagicMock()

        result = delete_prompt(self.mock_db, "test-prompt")

        self.assertTrue(result)
        self.mock_db.delete.assert_called_once()
        self.mock_db.commit.assert_called_once()

    def test_delete_prompt_not_found(self):
        """Test hard deleting a non-existent prompt."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = delete_prompt(self.mock_db, "nonexistent")

        self.assertFalse(result)

    def test_prompt_exists(self):
        """Test checking if a prompt exists."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_prompt

        result = prompt_exists(self.mock_db, "test-prompt")

        self.assertTrue(result)

    def test_prompt_not_exists(self):
        """Test checking if a non-existent prompt exists."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = prompt_exists(self.mock_db, "nonexistent")

        self.assertFalse(result)

    def test_reactivate_prompt(self):
        """Test reactivating a soft-deleted prompt."""
        inactive_prompt = PromptDB(
            id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            is_active=False,
        )
        self.mock_db.query.return_value.filter.return_value.first.return_value = inactive_prompt
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        result = reactivate_prompt(self.mock_db, "test-prompt")

        self.assertIsNotNone(result)
        self.mock_db.commit.assert_called_once()

    def test_reactivate_prompt_not_found(self):
        """Test reactivating a non-existent prompt."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = reactivate_prompt(self.mock_db, "nonexistent")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
