import logging
from typing import Any

from api.services.models import PushPromptRequest, ToolSchema
from api.services.prompts_client import PromptsServiceClient
from prompts.models import PromptData
from prompts.storage.base import PromptStorageBackend

logger = logging.getLogger(__name__)


class PromptsServiceStorage(PromptStorageBackend):
    """Storage backend that delegates to the external prompts service.

    This backend wraps PromptsServiceClient to provide the PromptStorageBackend
    interface, allowing the external prompts service to be used as a pluggable
    storage option via PROMPT_STORAGE_BACKEND=service.

    Note: The external service uses 'name' as the primary identifier, so
    prompt_id and name are treated as equivalent in this implementation.
    """

    def __init__(self):
        """Initialize with a PromptsServiceClient instance."""
        self.client = PromptsServiceClient()

    def _to_prompt_data(self, name: str, response: Any) -> PromptData:
        """Convert PullPromptResponse to PromptData.

        Args:
            name: The prompt name/id
            response: PullPromptResponse from the service

        Returns:
            PromptData with defaults for missing fields
        """
        # Convert ToolSchema objects to dicts if present
        tools: list[dict[str, Any]] = []
        if response.tools:
            for tool in response.tools:
                if isinstance(tool, ToolSchema):
                    tools.append(tool.model_dump())
                elif isinstance(tool, dict):
                    tools.append(tool)

        return PromptData(
            id=name,
            name=response.name,
            template=response.template,
            description=response.description,
            tags=response.tags or [],
            tools=tools,
            version=1,  # External service doesn't track versions
            created_at=None,  # External service doesn't provide timestamps
            updated_at=None,
            is_active=True,
        )

    def _to_push_request(
        self,
        name: str,
        template: str,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PushPromptRequest:
        """Convert parameters to PushPromptRequest.

        Args:
            name: Prompt name
            template: Prompt template
            description: Optional description
            tags: Optional tags
            tools: Optional tool configurations

        Returns:
            PushPromptRequest for the service
        """
        tool_schemas: list[ToolSchema] | None = None
        if tools:
            tool_schemas = [
                ToolSchema(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                )
                for t in tools
            ]

        return PushPromptRequest(
            name=name,
            raw_template=template,
            description=description,
            tags=tags,
            tools=tool_schemas,
        )

    def create(
        self,
        prompt_id: str,
        name: str,
        template: str,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PromptData:
        """Create a new prompt in the external service.

        Note: The external service uses POST for upsert (create or update).

        Args:
            prompt_id: Unique identifier (used as name in external service)
            name: Human-readable name
            template: The prompt template text
            description: Optional description
            tags: Optional list of tags
            tools: Optional list of tool configurations

        Returns:
            The created PromptData

        Raises:
            RuntimeError: If creation fails
        """
        # Use prompt_id as the name for the external service
        request = self._to_push_request(
            name=prompt_id,
            template=template,
            description=description,
            tags=tags,
            tools=tools,
        )

        success = self.client.create_prompt(request)
        if not success:
            raise RuntimeError(f"Failed to create prompt '{prompt_id}' in external service")

        # Fetch the created prompt to return complete data
        response = self.client.get_prompt(prompt_id)
        if response is None:
            # Return what we know even if fetch fails
            return PromptData(
                id=prompt_id,
                name=name,
                template=template,
                description=description,
                tags=tags or [],
                tools=tools or [],
                version=1,
                is_active=True,
            )

        result = self._to_prompt_data(prompt_id, response)
        # Override name with the provided human-readable name
        result.name = name
        logger.info(f"Created prompt '{prompt_id}' in external service")
        return result

    def get(self, prompt_id: str) -> PromptData | None:
        """Get a prompt by ID from the external service.

        Args:
            prompt_id: The prompt identifier (same as name in external service)

        Returns:
            PromptData if found, None otherwise
        """
        response = self.client.get_prompt(prompt_id)
        if response is None:
            return None
        return self._to_prompt_data(prompt_id, response)

    def get_all(self) -> list[PromptData]:
        """Get all prompts from the external service.

        Returns:
            List of all prompts
        """
        prompt_names = self.client.list_prompts()
        prompts: list[PromptData] = []

        for name in prompt_names:
            response = self.client.get_prompt(name)
            if response:
                prompts.append(self._to_prompt_data(name, response))

        return prompts

    def update(
        self,
        prompt_id: str,
        name: str | None = None,
        template: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PromptData | None:
        """Update an existing prompt in the external service.

        Uses POST (upsert) to update the prompt.

        Args:
            prompt_id: The prompt identifier
            name: New name (if updating)
            template: New template (if updating)
            description: New description (if updating)
            tags: New tags (if updating)
            tools: New tools configuration (if updating)

        Returns:
            Updated PromptData if successful, None if not found
        """
        # Get existing prompt to merge with updates
        existing = self.get(prompt_id)
        if existing is None:
            return None

        # Merge updates with existing values
        updated_template = template if template is not None else existing.template
        updated_description = description if description is not None else existing.description
        updated_tags = tags if tags is not None else existing.tags
        updated_tools = tools if tools is not None else existing.tools

        request = self._to_push_request(
            name=prompt_id,
            template=updated_template,
            description=updated_description,
            tags=updated_tags,
            tools=updated_tools,
        )

        success = self.client.create_prompt(request)
        if not success:
            logger.error(f"Failed to update prompt '{prompt_id}' in external service")
            return None

        # Fetch updated prompt
        response = self.client.get_prompt(prompt_id)
        if response is None:
            return None

        result = self._to_prompt_data(prompt_id, response)
        # Use provided name or keep existing
        if name:
            result.name = name
        logger.info(f"Updated prompt '{prompt_id}' in external service")
        return result

    def delete(self, prompt_id: str) -> bool:
        """Delete a prompt from the external service.

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if deleted, False if not found or failed
        """
        return self.client.delete_prompt(prompt_id)

    def exists(self, prompt_id: str) -> bool:
        """Check if a prompt exists in the external service.

        Args:
            prompt_id: The prompt identifier

        Returns:
            True if exists, False otherwise
        """
        response = self.client.get_prompt(prompt_id)
        return response is not None
