import unittest

from prompts.models import PromptData
from prompts.service import PromptService
from prompts.storage.base import PromptStorageBackend


class MockStorage(PromptStorageBackend):
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

    def update(self, prompt_id, name=None, template=None, description=None, tags=None, tools=None):
        if prompt_id not in self.prompts:
            return None
        prompt = self.prompts[prompt_id]
        if name is not None:
            prompt.name = name
        if template is not None:
            prompt.template = template
        if description is not None:
            prompt.description = description
        if tags is not None:
            prompt.tags = tags
        if tools is not None:
            prompt.tools = tools
        prompt.version += 1
        return prompt

    def delete(self, prompt_id):
        if prompt_id in self.prompts:
            del self.prompts[prompt_id]
            return True
        return False

    def exists(self, prompt_id):
        return prompt_id in self.prompts


class TestPromptService(unittest.TestCase):
    """Tests for PromptService class."""

    def setUp(self):
        self.storage = MockStorage()
        self.service = PromptService(self.storage)

    def test_create_prompt(self):
        prompt = self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
            description="A test prompt",
            tags=["test"],
        )

        self.assertEqual(prompt.id, "test-prompt")
        self.assertEqual(prompt.name, "Test Prompt")
        self.assertEqual(prompt.tags, ["test"])

    def test_create_prompt_duplicate(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        with self.assertRaises(ValueError) as context:
            self.service.create_prompt(
                prompt_id="test-prompt",
                name="Duplicate",
                template="Another template here.",
            )

        self.assertIn("already exists", str(context.exception))

    def test_create_prompt_invalid_template(self):
        with self.assertRaises(ValueError) as context:
            self.service.create_prompt(
                prompt_id="test-prompt",
                name="Test",
                template="Hi",  # Too short
            )

        self.assertIn("Invalid template", str(context.exception))

    def test_create_prompt_skip_validation(self):
        # Should not raise even with short template
        prompt = self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test",
            template="Hi",
            validate=False,
        )
        self.assertEqual(prompt.template, "Hi")

    def test_get_prompt(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        prompt = self.service.get_prompt("test-prompt")
        self.assertIsNotNone(prompt)
        assert prompt is not None  # for mypy
        self.assertEqual(prompt.name, "Test Prompt")

    def test_get_prompt_not_found(self):
        prompt = self.service.get_prompt("nonexistent")
        self.assertIsNone(prompt)

    def test_get_all_prompts(self):
        self.service.create_prompt(
            prompt_id="prompt-1",
            name="Prompt 1",
            template="Template one content here.",
        )
        self.service.create_prompt(
            prompt_id="prompt-2",
            name="Prompt 2",
            template="Template two content here.",
        )

        prompts = self.service.get_all_prompts()
        self.assertEqual(len(prompts), 2)

    def test_update_prompt(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Original Name",
            template="You are a helpful assistant.",
        )

        updated = self.service.update_prompt(
            prompt_id="test-prompt",
            name="Updated Name",
        )

        self.assertIsNotNone(updated)
        assert updated is not None  # for mypy
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.version, 2)

    def test_update_prompt_not_found(self):
        updated = self.service.update_prompt(
            prompt_id="nonexistent",
            name="New Name",
        )
        self.assertIsNone(updated)

    def test_delete_prompt(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        result = self.service.delete_prompt("test-prompt")
        self.assertTrue(result)

        prompt = self.service.get_prompt("test-prompt")
        self.assertIsNone(prompt)

    def test_delete_prompt_not_found(self):
        result = self.service.delete_prompt("nonexistent")
        self.assertFalse(result)

    def test_prompt_exists(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        self.assertTrue(self.service.prompt_exists("test-prompt"))
        self.assertFalse(self.service.prompt_exists("nonexistent"))

    def test_get_or_create_prompt_new(self):
        prompt, created = self.service.get_or_create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        self.assertTrue(created)
        self.assertEqual(prompt.id, "test-prompt")

    def test_get_or_create_prompt_existing(self):
        self.service.create_prompt(
            prompt_id="test-prompt",
            name="Test Prompt",
            template="You are a helpful assistant.",
        )

        prompt, created = self.service.get_or_create_prompt(
            prompt_id="test-prompt",
            name="Different Name",
            template="Different template content.",
        )

        self.assertFalse(created)
        self.assertEqual(prompt.name, "Test Prompt")  # Original name preserved


if __name__ == "__main__":
    unittest.main()
