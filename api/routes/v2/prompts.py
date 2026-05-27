import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from prompts.service import PromptService
from prompts.storage import get_prompt_storage

router = APIRouter(prefix="/prompts", tags=["Prompts"])
logger = logging.getLogger(__name__)


# Request/Response Models
class PromptCreate(BaseModel):
    """Request model for creating a prompt."""

    id: str = Field(..., description="Unique identifier for the prompt")
    name: str = Field(..., description="Human-readable name")
    template: str = Field(..., description="The prompt template text")
    description: str | None = Field(None, description="Optional description")
    tags: list[str] | None = Field(None, description="Optional tags for categorization")
    tools: list[dict[str, Any]] | None = Field(None, description="Optional tool configurations")


class PromptUpdate(BaseModel):
    """Request model for updating a prompt."""

    name: str | None = Field(None, description="New name")
    template: str | None = Field(None, description="New template text")
    description: str | None = Field(None, description="New description")
    tags: list[str] | None = Field(None, description="New tags")
    tools: list[dict[str, Any]] | None = Field(None, description="New tool configurations")


class PromptResponse(BaseModel):
    """Response model for a prompt."""

    id: str
    name: str
    template: str
    description: str | None = None
    tags: list[str] = []
    tools: list[dict[str, Any]] = []
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None
    is_active: bool = True


class PromptListResponse(BaseModel):
    """Response model for listing prompts."""

    prompts: list[PromptResponse]
    total: int


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    id: str | None = None


def get_prompt_service(db: Session = Depends(get_db)) -> PromptService:
    """Dependency to get PromptService instance."""
    storage = get_prompt_storage(db)
    return PromptService(storage)


@router.post("", response_model=PromptResponse, status_code=201)
async def create_prompt(
    prompt_data: PromptCreate,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Create a new prompt.

    Creates a prompt template that can be referenced by agents.
    """
    try:
        prompt = service.create_prompt(
            prompt_id=prompt_data.id,
            name=prompt_data.name,
            template=prompt_data.template,
            description=prompt_data.description,
            tags=prompt_data.tags,
            tools=prompt_data.tools,
        )
        return PromptResponse(
            id=prompt.id,
            name=prompt.name,
            template=prompt.template,
            description=prompt.description,
            tags=prompt.tags,
            tools=prompt.tools,
            version=prompt.version,
            created_at=prompt.created_at.isoformat() if prompt.created_at else None,
            updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
            is_active=prompt.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to create prompt")


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    service: PromptService = Depends(get_prompt_service),
) -> PromptListResponse:
    """List all active prompts."""
    prompts = service.get_all_prompts()
    return PromptListResponse(
        prompts=[
            PromptResponse(
                id=p.id,
                name=p.name,
                template=p.template,
                description=p.description,
                tags=p.tags,
                tools=p.tools,
                version=p.version,
                created_at=p.created_at.isoformat() if p.created_at else None,
                updated_at=p.updated_at.isoformat() if p.updated_at else None,
                is_active=p.is_active,
            )
            for p in prompts
        ],
        total=len(prompts),
    )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: str,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Get a prompt by ID."""
    prompt = service.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    return PromptResponse(
        id=prompt.id,
        name=prompt.name,
        template=prompt.template,
        description=prompt.description,
        tags=prompt.tags,
        tools=prompt.tools,
        version=prompt.version,
        created_at=prompt.created_at.isoformat() if prompt.created_at else None,
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
        is_active=prompt.is_active,
    )


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    prompt_data: PromptUpdate,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Update an existing prompt."""
    try:
        prompt = service.update_prompt(
            prompt_id=prompt_id,
            name=prompt_data.name,
            template=prompt_data.template,
            description=prompt_data.description,
            tags=prompt_data.tags,
            tools=prompt_data.tools,
        )
        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

        return PromptResponse(
            id=prompt.id,
            name=prompt.name,
            template=prompt.template,
            description=prompt.description,
            tags=prompt.tags,
            tools=prompt.tools,
            version=prompt.version,
            created_at=prompt.created_at.isoformat() if prompt.created_at else None,
            updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
            is_active=prompt.is_active,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error updating prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to update prompt")


@router.delete("/{prompt_id}", response_model=MessageResponse)
async def delete_prompt(
    prompt_id: str,
    service: PromptService = Depends(get_prompt_service),
) -> MessageResponse:
    """Delete a prompt (soft delete)."""
    result = service.delete_prompt(prompt_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    return MessageResponse(message="Prompt deleted successfully", id=prompt_id)
