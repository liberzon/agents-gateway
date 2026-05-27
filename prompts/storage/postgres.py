import json
from typing import Any

from sqlalchemy.orm import Session

from db.db_models import PromptDB
from db.prompt_crud import (
    create_prompt as db_create_prompt,
)
from db.prompt_crud import (
    delete_prompt as db_delete_prompt,
)
from db.prompt_crud import (
    get_all_prompts as db_get_all_prompts,
)
from db.prompt_crud import (
    get_prompt as db_get_prompt,
)
from db.prompt_crud import (
    prompt_exists as db_prompt_exists,
)
from db.prompt_crud import (
    soft_delete_prompt as db_soft_delete_prompt,
)
from db.prompt_crud import (
    update_prompt as db_update_prompt,
)
from prompts.models import PromptData
from prompts.storage.base import PromptStorageBackend


class PostgresStorage(PromptStorageBackend):
    """PostgreSQL-based prompt storage backend."""

    def __init__(self, db: Session):
        """Initialize with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def _to_prompt_data(self, prompt_db: PromptDB) -> PromptData:
        """Convert database model to PromptData."""
        tags = []
        if prompt_db.tags:
            try:
                tags = json.loads(prompt_db.tags)  # type: ignore[arg-type]
            except json.JSONDecodeError:
                tags = []

        tools = []
        if prompt_db.tools:
            try:
                tools = json.loads(prompt_db.tools)  # type: ignore[arg-type]
            except json.JSONDecodeError:
                tools = []

        return PromptData(
            id=prompt_db.id,  # type: ignore[arg-type]
            name=prompt_db.name,  # type: ignore[arg-type]
            template=prompt_db.template,  # type: ignore[arg-type]
            description=prompt_db.description,  # type: ignore[arg-type]
            tags=tags,
            tools=tools,
            version=prompt_db.version,  # type: ignore[arg-type]
            created_at=prompt_db.created_at,  # type: ignore[arg-type]
            updated_at=prompt_db.updated_at,  # type: ignore[arg-type]
            is_active=prompt_db.is_active,  # type: ignore[arg-type]
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
        """Create a new prompt in PostgreSQL."""
        prompt_db = db_create_prompt(
            db=self.db,
            prompt_id=prompt_id,
            name=name,
            template=template,
            description=description,
            tags=tags,
            tools=tools,
        )
        return self._to_prompt_data(prompt_db)

    def get(self, prompt_id: str) -> PromptData | None:
        """Get a prompt by ID from PostgreSQL."""
        prompt_db = db_get_prompt(self.db, prompt_id)
        if prompt_db is None:
            return None
        return self._to_prompt_data(prompt_db)

    def get_all(self) -> list[PromptData]:
        """Get all active prompts from PostgreSQL."""
        prompts_db = db_get_all_prompts(self.db)
        return [self._to_prompt_data(p) for p in prompts_db]

    def update(
        self,
        prompt_id: str,
        name: str | None = None,
        template: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> PromptData | None:
        """Update a prompt in PostgreSQL."""
        prompt_db = db_update_prompt(
            db=self.db,
            prompt_id=prompt_id,
            name=name,
            template=template,
            description=description,
            tags=tags,
            tools=tools,
        )
        if prompt_db is None:
            return None
        return self._to_prompt_data(prompt_db)

    def delete(self, prompt_id: str) -> bool:
        """Soft delete a prompt in PostgreSQL."""
        return db_soft_delete_prompt(self.db, prompt_id)

    def hard_delete(self, prompt_id: str) -> bool:
        """Hard delete a prompt in PostgreSQL."""
        return db_delete_prompt(self.db, prompt_id)

    def exists(self, prompt_id: str) -> bool:
        """Check if a prompt exists in PostgreSQL."""
        return db_prompt_exists(self.db, prompt_id)
