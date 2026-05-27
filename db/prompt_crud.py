import datetime
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from db.db_models import PromptDB

logger = logging.getLogger(__name__)


def create_prompt(
    db: Session,
    prompt_id: str,
    name: str,
    template: str,
    description: str | None = None,
    tags: list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> PromptDB:
    """Create a new prompt in the database."""
    prompt = PromptDB(
        id=prompt_id,
        name=name,
        template=template,
        description=description,
        tags=json.dumps(tags) if tags else None,
        tools=json.dumps(tools) if tools else None,
        version=1,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        is_active=True,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    logger.info(f"Created prompt: {prompt_id}")
    return prompt


def get_prompt(db: Session, prompt_id: str) -> PromptDB | None:
    """Get a prompt by ID."""
    return db.query(PromptDB).filter(PromptDB.id == prompt_id, PromptDB.is_active.is_(True)).first()


def get_all_prompts(db: Session, include_inactive: bool = False) -> list[PromptDB]:
    """Get all prompts."""
    query = db.query(PromptDB)
    if not include_inactive:
        query = query.filter(PromptDB.is_active.is_(True))
    return query.order_by(PromptDB.created_at.desc()).all()


def update_prompt(
    db: Session,
    prompt_id: str,
    name: str | None = None,
    template: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> PromptDB | None:
    """Update an existing prompt. Returns None if not found."""
    prompt = get_prompt(db, prompt_id)
    if not prompt:
        return None

    if name is not None:
        prompt.name = name  # type: ignore[assignment]
    if template is not None:
        prompt.template = template  # type: ignore[assignment]
    if description is not None:
        prompt.description = description  # type: ignore[assignment]
    if tags is not None:
        prompt.tags = json.dumps(tags)  # type: ignore[assignment]
    if tools is not None:
        prompt.tools = json.dumps(tools)  # type: ignore[assignment]

    # Increment version on update
    prompt.version = prompt.version + 1  # type: ignore[assignment, operator]
    prompt.updated_at = datetime.datetime.utcnow()  # type: ignore[assignment]

    db.commit()
    db.refresh(prompt)
    logger.info(f"Updated prompt: {prompt_id} to version {prompt.version}")
    return prompt


def soft_delete_prompt(db: Session, prompt_id: str) -> bool:
    """Soft delete a prompt (set is_active to False)."""
    prompt = get_prompt(db, prompt_id)
    if not prompt:
        return False

    prompt.is_active = False  # type: ignore[assignment]
    prompt.updated_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    logger.info(f"Soft deleted prompt: {prompt_id}")
    return True


def delete_prompt(db: Session, prompt_id: str) -> bool:
    """Hard delete a prompt from the database."""
    prompt = db.query(PromptDB).filter(PromptDB.id == prompt_id).first()
    if not prompt:
        return False

    db.delete(prompt)
    db.commit()
    logger.info(f"Hard deleted prompt: {prompt_id}")
    return True


def prompt_exists(db: Session, prompt_id: str) -> bool:
    """Check if a prompt exists (active or inactive)."""
    return db.query(PromptDB).filter(PromptDB.id == prompt_id).first() is not None


def reactivate_prompt(db: Session, prompt_id: str) -> PromptDB | None:
    """Reactivate a soft-deleted prompt."""
    prompt = db.query(PromptDB).filter(PromptDB.id == prompt_id, PromptDB.is_active.is_(False)).first()
    if not prompt:
        return None

    prompt.is_active = True  # type: ignore[assignment]
    prompt.updated_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    db.refresh(prompt)
    logger.info(f"Reactivated prompt: {prompt_id}")
    return prompt
