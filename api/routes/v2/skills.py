import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from db.skill_crud import (
    create_skill,
    get_all_skills,
    get_skill,
    soft_delete_skill,
    update_skill,
)

v2_skills_router = APIRouter(prefix="/skills", tags=["V2 Skills"])


class SkillCreate(BaseModel):
    """Request model for creating a new skill"""

    id: str = Field(..., max_length=255)
    name: str = Field(..., max_length=255)
    instructions: str
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=255)
    references: Optional[List[Dict[str, Any]]] = None
    scripts: Optional[List[Dict[str, Any]]] = None
    allowed_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SkillUpdate(BaseModel):
    """Request model for updating an existing skill"""

    name: Optional[str] = Field(default=None, max_length=255)
    instructions: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=255)
    references: Optional[List[Dict[str, Any]]] = None
    scripts: Optional[List[Dict[str, Any]]] = None
    allowed_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SkillResponse(BaseModel):
    """Response model for a single skill"""

    id: str
    name: str
    instructions: str
    description: Optional[str] = None
    category: Optional[str] = None
    references: Optional[List[Dict[str, Any]]] = None
    scripts: Optional[List[Dict[str, Any]]] = None
    allowed_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True


class SkillInfo(BaseModel):
    """Lightweight skill model for list responses"""

    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool = True


def _parse_json_field(value: Any) -> Optional[List[Any]]:
    """Parse a JSON string field from the database, returning None if empty."""
    if not value:
        return None
    try:
        return json.loads(value)  # type: ignore[arg-type]
    except (json.JSONDecodeError, TypeError):
        return None


def _skill_to_response(db_skill: Any) -> SkillResponse:
    """Convert a SkillDB instance to a SkillResponse."""
    return SkillResponse(
        id=db_skill.id,  # type: ignore[arg-type]
        name=db_skill.name,  # type: ignore[arg-type]
        instructions=db_skill.instructions,  # type: ignore[arg-type]
        description=db_skill.description,  # type: ignore[arg-type]
        category=db_skill.category,  # type: ignore[arg-type]
        references=_parse_json_field(db_skill.references),
        scripts=_parse_json_field(db_skill.scripts),
        allowed_tools=_parse_json_field(db_skill.allowed_tools),
        tags=_parse_json_field(db_skill.tags),
        created_at=db_skill.created_at,  # type: ignore[arg-type]
        updated_at=db_skill.updated_at,  # type: ignore[arg-type]
        is_active=db_skill.is_active,  # type: ignore[arg-type]
    )


def _skill_to_info(db_skill: Any) -> SkillInfo:
    """Convert a SkillDB instance to a SkillInfo."""
    return SkillInfo(
        id=db_skill.id,  # type: ignore[arg-type]
        name=db_skill.name,  # type: ignore[arg-type]
        description=db_skill.description,  # type: ignore[arg-type]
        category=db_skill.category,  # type: ignore[arg-type]
        tags=_parse_json_field(db_skill.tags),
        is_active=db_skill.is_active,  # type: ignore[arg-type]
    )


@v2_skills_router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill_v2(body: SkillCreate, db: Session = Depends(get_db)):
    """
    Create a new skill with the provided configuration.

    Args:
        body: Skill creation request
        db: Database session

    Returns:
        SkillResponse: Created skill details
    """
    logging.info(f"Request to create new skill: {body.id}")

    # Check if skill already exists
    existing = get_skill(db, body.id)
    if existing:
        logging.error(f"Skill {body.id} already exists")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Skill {body.id} already exists")

    try:
        db_skill = create_skill(
            db=db,
            skill_id=body.id,
            name=body.name,
            instructions=body.instructions,
            description=body.description,
            category=body.category,
            references=body.references,
            scripts=body.scripts,
            allowed_tools=body.allowed_tools,
            tags=body.tags,
        )
        logging.info(f"Skill {body.id} created successfully")
        return _skill_to_response(db_skill)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error creating skill {body.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create skill {body.id}: {str(e)}"
        )


@v2_skills_router.get("", response_model=List[SkillInfo])
async def list_skills_v2(
    include_inactive: bool = False,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns a list of all available skills.

    Args:
        include_inactive: Whether to include inactive skills
        category: Optional category filter
        db: Database session

    Returns:
        List[SkillInfo]: List of skill information objects
    """
    logging.info("Request to list all available skills (v2)")

    db_skills = get_all_skills(db, include_inactive=include_inactive, category=category)

    skills = [_skill_to_info(db_skill) for db_skill in db_skills]

    logging.info(f"Returning {len(skills)} available skills (v2)")
    return skills


@v2_skills_router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill_v2(skill_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific skill.

    Args:
        skill_id: The ID of the skill to get
        db: Database session

    Returns:
        SkillResponse: Skill details
    """
    logging.info(f"Request for skill info: {skill_id}")

    db_skill = get_skill(db, skill_id)
    if not db_skill:
        logging.error(f"Skill {skill_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill {skill_id} not found")

    return _skill_to_response(db_skill)


@v2_skills_router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill_v2(skill_id: str, body: SkillUpdate, db: Session = Depends(get_db)):
    """
    Update an existing skill.

    Args:
        skill_id: The ID of the skill to update
        body: Skill update request with fields to update
        db: Database session

    Returns:
        SkillResponse: Updated skill details
    """
    logging.info(f"Request to update skill: {skill_id}")

    db_skill = update_skill(
        db=db,
        skill_id=skill_id,
        name=body.name,
        instructions=body.instructions,
        description=body.description,
        category=body.category,
        references=body.references,
        scripts=body.scripts,
        allowed_tools=body.allowed_tools,
        tags=body.tags,
    )

    if not db_skill:
        logging.error(f"Skill {skill_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill {skill_id} not found")

    logging.info(f"Skill {skill_id} updated successfully")
    return _skill_to_response(db_skill)


@v2_skills_router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill_v2(skill_id: str, db: Session = Depends(get_db)):
    """
    Soft delete a skill by setting it as inactive.

    Args:
        skill_id: The ID of the skill to delete
        db: Database session

    Returns:
        No content on success
    """
    logging.info(f"Request to delete skill: {skill_id}")

    success = soft_delete_skill(db, skill_id)
    if not success:
        logging.error(f"Skill {skill_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill {skill_id} not found")

    logging.info(f"Skill {skill_id} soft deleted successfully")
    return None
