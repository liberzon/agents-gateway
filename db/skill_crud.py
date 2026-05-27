import datetime
import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from db.db_models import SkillDB


def create_skill(
    db: Session,
    skill_id: str,
    name: str,
    instructions: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    references: Optional[List[dict]] = None,
    scripts: Optional[List[dict]] = None,
    allowed_tools: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> SkillDB:
    """
    Create a new Skill record or reactivate an existing inactive one.

    Args:
        db: Database session
        skill_id: Unique skill identifier
        name: Display name for the skill
        instructions: Skill instructions text
        description: Optional description
        category: Optional category for grouping
        references: Optional list of reference objects [{name, content}]
        scripts: Optional list of script objects [{name, content}]
        allowed_tools: Optional list of allowed tool names
        tags: Optional list of tags

    Returns:
        Created or reactivated Skill instance
    """
    try:
        tags_json = json.dumps(tags) if tags else None
        references_json = json.dumps(references) if references else None
        scripts_json = json.dumps(scripts) if scripts else None
        allowed_tools_json = json.dumps(allowed_tools) if allowed_tools else None

        # Check if there's an inactive skill with the same ID
        existing_skill = db.query(SkillDB).filter(SkillDB.id == skill_id, ~SkillDB.is_active).first()

        if existing_skill:
            # Reactivate and update the existing skill
            existing_skill.name = name  # type: ignore[assignment]
            existing_skill.instructions = instructions  # type: ignore[assignment]
            existing_skill.description = description  # type: ignore[assignment]
            existing_skill.category = category  # type: ignore[assignment]
            existing_skill.references = references_json  # type: ignore[assignment]
            existing_skill.scripts = scripts_json  # type: ignore[assignment]
            existing_skill.allowed_tools = allowed_tools_json  # type: ignore[assignment]
            existing_skill.tags = tags_json  # type: ignore[assignment]
            existing_skill.is_active = True  # type: ignore[assignment]
            existing_skill.updated_at = datetime.datetime.utcnow()  # type: ignore[assignment]

            db.commit()
            db.refresh(existing_skill)

            logging.info(f"Reactivated existing Skill for {skill_id}")
            return existing_skill
        else:
            # Create a new skill
            skill = SkillDB(
                id=skill_id,
                name=name,
                instructions=instructions,
                description=description,
                category=category,
                references=references_json,
                scripts=scripts_json,
                allowed_tools=allowed_tools_json,
                tags=tags_json,
                is_active=True,
            )

            db.add(skill)
            db.commit()
            db.refresh(skill)

            logging.info(f"Created new Skill for {skill_id}")
            return skill
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating skill: {e}")
        raise


def get_skill(db: Session, skill_id: str) -> Optional[SkillDB]:
    """
    Get Skill by skill_id.

    Args:
        db: Database session
        skill_id: Skill identifier

    Returns:
        SkillDB instance or None if not found
    """
    return db.query(SkillDB).filter(SkillDB.id == skill_id, SkillDB.is_active).first()


def get_all_skills(
    db: Session,
    include_inactive: bool = False,
    category: Optional[str] = None,
) -> List[SkillDB]:
    """
    Get all Skill records.

    Args:
        db: Database session
        include_inactive: Whether to include inactive skills
        category: Optional category filter

    Returns:
        List of SkillDB instances
    """
    query = db.query(SkillDB)
    if not include_inactive:
        query = query.filter(SkillDB.is_active)
    if category is not None:
        query = query.filter(SkillDB.category == category)

    return query.order_by(SkillDB.name).all()


def update_skill(
    db: Session,
    skill_id: str,
    name: Optional[str] = None,
    instructions: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    references: Optional[List[dict]] = None,
    scripts: Optional[List[dict]] = None,
    allowed_tools: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Optional[SkillDB]:
    """
    Update an existing Skill record.

    Args:
        db: Database session
        skill_id: Skill identifier
        name: New name (optional)
        instructions: New instructions (optional)
        description: New description (optional)
        category: New category (optional)
        references: New references (optional)
        scripts: New scripts (optional)
        allowed_tools: New allowed tools (optional)
        tags: New tags (optional)

    Returns:
        Updated Skill instance or None if not found
    """
    skill = get_skill(db, skill_id)
    if not skill:
        return None

    if name is not None:
        skill.name = name  # type: ignore[assignment]
    if instructions is not None:
        skill.instructions = instructions  # type: ignore[assignment]
    if description is not None:
        skill.description = description  # type: ignore[assignment]
    if category is not None:
        skill.category = category  # type: ignore[assignment]
    if references is not None:
        skill.references = json.dumps(references)  # type: ignore[assignment]
    if scripts is not None:
        skill.scripts = json.dumps(scripts)  # type: ignore[assignment]
    if allowed_tools is not None:
        skill.allowed_tools = json.dumps(allowed_tools)  # type: ignore[assignment]
    if tags is not None:
        skill.tags = json.dumps(tags)  # type: ignore[assignment]

    db.commit()
    db.refresh(skill)

    logging.info(f"Updated Skill for {skill_id}")
    return skill


def soft_delete_skill(db: Session, skill_id: str) -> bool:
    """
    Soft delete a Skill record by setting is_active to False.

    Args:
        db: Database session
        skill_id: Skill identifier

    Returns:
        True if deleted, False if not found
    """
    skill = get_skill(db, skill_id)
    if not skill:
        return False

    skill.is_active = False  # type: ignore[assignment]
    db.commit()

    logging.info(f"Soft deleted Skill for {skill_id}")
    return True


def delete_skill(db: Session, skill_id: str) -> bool:
    """
    Hard delete a Skill record from the database.

    Args:
        db: Database session
        skill_id: Skill identifier

    Returns:
        True if deleted, False if not found
    """
    try:
        skill = db.query(SkillDB).filter(SkillDB.id == skill_id).first()

        if not skill:
            logging.warning(f"Skill not found for deletion: {skill_id}")
            return False

        db.delete(skill)
        db.commit()

        logging.info(f"Hard deleted Skill for {skill_id}")
        return True
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting skill: {e}")
        raise
