from abc import ABC, abstractmethod
from typing import Any

from prompts.models import PromptData


class PromptStorageBackend(ABC):
    """Abstract base class for prompt storage backends."""

    @abstractmethod
    def create(
        self,
        prompt_id: str,
        name: str,
        template: str,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PromptData:
        """Create a new prompt.

        Args:
            prompt_id: Unique identifier for the prompt
            name: Human-readable name
            template: The prompt template text
            description: Optional description
            tags: Optional list of tags
            tools: Optional list of tool configurations

        Returns:
            The created PromptData
        """
        pass

    @abstractmethod
    def get(self, prompt_id: str) -> PromptData | None:
        """Get a prompt by ID.

        Args:
            prompt_id: The prompt identifier

        Returns:
            PromptData if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all(self) -> list[PromptData]:
        """Get all active prompts.

        Returns:
            List of all active prompts
        """
        pass

    @abstractmethod
    def update(
        self,
        prompt_id: str,
        name: str | None = None,
        template: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PromptData | None:
        """Update an existing prompt.

        Args:
            prompt_id: The prompt identifier
            name: New name (if updating)
            template: New template (if updating)
            description: New description (if updating)
            tags: New tags (if updating)
            tools: New tools configuration (if updating)

        Returns:
            Updated PromptData if found, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, prompt_id: str) -> bool:
        """Delete a prompt (soft delete).

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, prompt_id: str) -> bool:
        """Check if a prompt exists.

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if exists, False otherwise
        """
        pass
