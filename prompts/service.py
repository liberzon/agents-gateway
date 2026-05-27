import logging
from typing import Any

from prompts.models import PromptData
from prompts.parser import normalize_template, validate_template
from prompts.storage.base import PromptStorageBackend

logger = logging.getLogger(__name__)


class PromptService:
    """High-level service for managing prompts.

    Provides business logic layer on top of storage backends.
    """

    def __init__(self, storage: PromptStorageBackend):
        """Initialize with a storage backend.

        Args:
            storage: The storage backend to use (PostgreSQL, LangSmith, etc.)
        """
        self.storage = storage

    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        template: str,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        validate: bool = True,
    ) -> PromptData:
        """Create a new prompt.

        Args:
            prompt_id: Unique identifier
            name: Human-readable name
            template: The prompt template
            description: Optional description
            tags: Optional tags for categorization
            tools: Optional tool configurations
            validate: Whether to validate the template (default: True)

        Returns:
            The created PromptData

        Raises:
            ValueError: If validation fails or prompt already exists
        """
        # Check if prompt already exists
        if self.storage.exists(prompt_id):
            raise ValueError(f"Prompt with id '{prompt_id}' already exists")

        # Validate template if requested
        if validate:
            is_valid, errors = validate_template(template)
            if not is_valid:
                raise ValueError(f"Invalid template: {', '.join(errors)}")

        # Normalize template
        normalized_template = normalize_template(template)

        # Create in storage
        prompt = self.storage.create(
            prompt_id=prompt_id,
            name=name,
            template=normalized_template,
            description=description,
            tags=tags,
            tools=tools,
        )

        logger.info(f"Created prompt: {prompt_id}")
        return prompt

    def get_prompt(self, prompt_id: str) -> PromptData | None:
        """Get a prompt by ID.

        Args:
            prompt_id: The prompt identifier

        Returns:
            PromptData if found, None otherwise
        """
        return self.storage.get(prompt_id)

    def get_all_prompts(self) -> list[PromptData]:
        """Get all active prompts.

        Returns:
            List of all active prompts
        """
        return self.storage.get_all()

    def update_prompt(
        self,
        prompt_id: str,
        name: str | None = None,
        template: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        validate: bool = True,
    ) -> PromptData | None:
        """Update an existing prompt.

        Args:
            prompt_id: The prompt identifier
            name: New name (if updating)
            template: New template (if updating)
            description: New description (if updating)
            tags: New tags (if updating)
            tools: New tools (if updating)
            validate: Whether to validate the template (default: True)

        Returns:
            Updated PromptData if found, None otherwise

        Raises:
            ValueError: If validation fails
        """
        # Validate template if provided and validation requested
        if template and validate:
            is_valid, errors = validate_template(template)
            if not is_valid:
                raise ValueError(f"Invalid template: {', '.join(errors)}")
            template = normalize_template(template)

        # Update in storage
        prompt = self.storage.update(
            prompt_id=prompt_id,
            name=name,
            template=template,
            description=description,
            tags=tags,
            tools=tools,
        )

        if prompt:
            logger.info(f"Updated prompt: {prompt_id} to version {prompt.version}")
        return prompt

    def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt (soft delete).

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if deleted, False if not found
        """
        result = self.storage.delete(prompt_id)
        if result:
            logger.info(f"Deleted prompt: {prompt_id}")
        return result

    def prompt_exists(self, prompt_id: str) -> bool:
        """Check if a prompt exists.

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if exists, False otherwise
        """
        return self.storage.exists(prompt_id)

    def get_or_create_prompt(
        self,
        prompt_id: str,
        name: str,
        template: str,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[PromptData, bool]:
        """Get an existing prompt or create a new one.

        Args:
            prompt_id: The prompt identifier
            name: Name for new prompt
            template: Template for new prompt
            description: Description for new prompt
            tags: Tags for new prompt
            tools: Tools for new prompt

        Returns:
            Tuple of (PromptData, created) where created is True if new
        """
        existing = self.storage.get(prompt_id)
        if existing:
            return existing, False

        created = self.create_prompt(
            prompt_id=prompt_id,
            name=name,
            template=template,
            description=description,
            tags=tags,
            tools=tools,
        )
        return created, True
