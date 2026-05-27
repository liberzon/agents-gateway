import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.services.knowledge_service import get_knowledge_service
from db.knowledge_crud import (
    create_knowledge_entry,
    delete_knowledge_entry,
    get_knowledge_entries,
    get_knowledge_entry,
    update_knowledge_entry,
)
from db.session import get_db

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# Async helper function for knowledge base creation with logging
async def log_knowledge_creation_result(db: Session, entry) -> bool:
    """Wrapper to log the boolean result from create_knowledge_base."""
    try:
        result = await get_knowledge_service().create_knowledge_base(db=db, entry=entry)
        logging.info(f"Knowledge base creation for file_id {entry.file_id} completed with result: {result}")
        return result
    except Exception as e:
        logging.error(f"Knowledge base creation for file_id {entry.file_id} failed with exception: {e}")
        return False


# Pydantic models for request/response
class KnowledgeEntryCreate(BaseModel):
    """Request model for creating knowledge entries."""

    file_id: str = Field(..., description="UUID of the source file")
    original_filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Type of file: 'company' or 'project'")
    content_type: Optional[str] = Field(None, description="MIME type of the file")
    gcs_path: Optional[str] = Field(None, description="Google Cloud Storage path")
    status: str = Field("active", description="File status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class KnowledgeEntryUpdate(BaseModel):
    """Request model for updating knowledge entries."""

    status: Optional[str] = Field(None, description="File status")
    knowledge_status: Optional[str] = Field(None, description="Knowledge indexing status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class KnowledgeEntryResponse(BaseModel):
    """Response model for knowledge entries."""

    id: str = Field(..., description="Knowledge entry ID")
    tenant_id: str = Field(..., description="Tenant ID")
    collection_id: Optional[str] = Field(None, description="Collection ID (null for tenant-level)")
    file_id: str = Field(..., description="Source file ID")
    original_filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type")
    content_type: Optional[str] = Field(None, description="Content type")
    gcs_path: Optional[str] = Field(None, description="GCS path")
    status: str = Field(..., description="File status")
    knowledge_status: str = Field(..., description="Knowledge status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    @classmethod
    def from_db_model(cls, db_model) -> "KnowledgeEntryResponse":
        """Convert database model to response model."""
        return cls(
            id=str(db_model.id),
            tenant_id=db_model.tenant_id,
            collection_id=db_model.collection_id,
            file_id=str(db_model.file_id),
            original_filename=db_model.original_filename,
            file_type=db_model.file_type,
            content_type=db_model.content_type,
            gcs_path=db_model.gcs_path,
            status=db_model.status,
            knowledge_status=db_model.knowledge_status,
            metadata=db_model.entry_metadata,
            created_at=db_model.created_at.isoformat(),
            updated_at=db_model.updated_at.isoformat(),
        )


class KnowledgeListResponse(BaseModel):
    """Response model for listing knowledge entries."""

    files: List[KnowledgeEntryResponse] = Field(..., description="List of knowledge entries")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")


class KnowledgeCreateResponse(BaseModel):
    """Response model for knowledge creation."""

    id: str = Field(..., description="Knowledge entry ID")
    tenant_id: str = Field(..., description="Tenant ID")
    collection_id: Optional[str] = Field(None, description="Collection ID")
    file_id: str = Field(..., description="Source file ID")
    status: str = Field(..., description="File status")
    knowledge_status: str = Field(..., description="Knowledge status")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    message: str = Field(..., description="Success message")


# Tenant Knowledge Endpoints


@router.post(
    "/{tenant_id}",
    response_model=KnowledgeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tenant knowledge entry",
)
async def create_tenant_knowledge(tenant_id: str, request: KnowledgeEntryCreate, db: Session = Depends(get_db)):
    """Create a new knowledge entry for tenant."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(request.file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        # Validate file_type
        if request.file_type not in ["company", "project"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="file_type must be either 'company' or 'project'"
            )

        entry = await create_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=request.file_id,
            original_filename=request.original_filename,
            file_type=request.file_type,
            collection_id=None,  # Tenant level
            content_type=request.content_type,
            gcs_path=request.gcs_path,
            status=request.status,
            knowledge_status="indexing",  # Always start with indexing
            metadata=request.metadata,
        )

        # Start knowledge base creation asynchronously without waiting for response
        asyncio.create_task(log_knowledge_creation_result(db=db, entry=entry))

        return KnowledgeCreateResponse(
            id=str(entry.id),
            tenant_id=str(entry.tenant_id),
            collection_id=str(entry.collection_id) if entry.collection_id else None,
            file_id=str(entry.file_id),
            status=str(entry.status),
            knowledge_status=str(entry.knowledge_status),
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
            message="File added to tenant knowledge base. Knowledge indexing is processing asynchronously.",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logging.error(f"Failed to create tenant knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create knowledge entry"
        )


@router.get("/{tenant_id}", response_model=KnowledgeListResponse, summary="List tenant knowledge entries")
async def list_tenant_knowledge(
    tenant_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """List knowledge entries for tenant."""
    try:
        entries, total_count = await get_knowledge_entries(
            db=db,
            tenant_id=tenant_id,
            collection_id=None,  # Tenant level
            limit=limit,
            offset=offset,
        )

        files = [KnowledgeEntryResponse.from_db_model(entry) for entry in entries]

        return KnowledgeListResponse(
            files=files,
            pagination={
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count,
            },
        )

    except Exception as e:
        logging.error(f"Failed to list tenant knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve knowledge entries"
        )


@router.get(
    "/{tenant_id}/files/{file_id}",
    response_model=KnowledgeEntryResponse,
    summary="Get tenant knowledge entry details",
)
async def get_tenant_knowledge_file(tenant_id: str, file_id: str, db: Session = Depends(get_db)):
    """Get specific tenant knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        entry = await get_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            collection_id=None,  # Tenant level
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

        return KnowledgeEntryResponse.from_db_model(entry)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get tenant knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve knowledge entry"
        )


@router.patch(
    "/{tenant_id}/files/{file_id}", response_model=KnowledgeEntryResponse, summary="Update tenant knowledge entry"
)
async def update_tenant_knowledge_file(
    tenant_id: str, file_id: str, request: KnowledgeEntryUpdate, db: Session = Depends(get_db)
):
    """Update tenant knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        # Build updates dict from non-None fields
        updates: Dict[str, Any] = {}
        if request.status is not None:
            updates["status"] = request.status
        if request.knowledge_status is not None:
            updates["knowledge_status"] = request.knowledge_status
        if request.metadata is not None:
            updates["entry_metadata"] = request.metadata

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update")

        entry = await update_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            updates=updates,
            collection_id=None,  # Tenant level
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

        return KnowledgeEntryResponse.from_db_model(entry)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to update tenant knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update knowledge entry"
        )


@router.delete(
    "/{tenant_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete tenant knowledge entry"
)
async def delete_tenant_knowledge_file(
    tenant_id: str,
    file_id: str,
    hard_delete: bool = Query(False, description="Permanently delete"),
    db: Session = Depends(get_db),
):
    """Delete tenant knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        success = await delete_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            collection_id=None,  # Tenant level
            hard_delete=hard_delete,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to delete tenant knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete knowledge entry"
        )


# Collection Knowledge Endpoints


@router.post(
    "/{tenant_id}/{collection_id}",
    response_model=KnowledgeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create collection knowledge entry",
)
async def create_collection_knowledge(
    tenant_id: str, collection_id: str, request: KnowledgeEntryCreate, db: Session = Depends(get_db)
):
    """Create a new knowledge entry for collection."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(request.file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        # Validate file_type
        if request.file_type not in ["company", "project"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="file_type must be either 'company' or 'project'"
            )

        entry = await create_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=request.file_id,
            original_filename=request.original_filename,
            file_type=request.file_type,
            collection_id=collection_id,  # Collection level
            content_type=request.content_type,
            gcs_path=request.gcs_path,
            status=request.status,
            knowledge_status="indexing",  # Always start with indexing
            metadata=request.metadata,
        )

        # Start knowledge base creation asynchronously without waiting for response
        asyncio.create_task(log_knowledge_creation_result(db=db, entry=entry))

        return KnowledgeCreateResponse(
            id=str(entry.id),
            tenant_id=str(entry.tenant_id),
            collection_id=str(entry.collection_id) if entry.collection_id else None,
            file_id=str(entry.file_id),
            status=str(entry.status),
            knowledge_status=str(entry.knowledge_status),
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
            message="File added to collection knowledge base. Knowledge indexing is processing asynchronously.",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logging.error(f"Failed to create collection knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create knowledge entry"
        )


@router.get(
    "/{tenant_id}/{collection_id}", response_model=KnowledgeListResponse, summary="List collection knowledge entries"
)
async def list_collection_knowledge(
    tenant_id: str,
    collection_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """List knowledge entries for collection."""
    try:
        entries, total_count = await get_knowledge_entries(
            db=db,
            tenant_id=tenant_id,
            collection_id=collection_id,  # Collection level
            limit=limit,
            offset=offset,
        )

        files = [KnowledgeEntryResponse.from_db_model(entry) for entry in entries]

        return KnowledgeListResponse(
            files=files,
            pagination={
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count,
            },
        )

    except Exception as e:
        logging.error(f"Failed to list collection knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve knowledge entries"
        )


@router.get(
    "/{tenant_id}/{collection_id}/files/{file_id}",
    response_model=KnowledgeEntryResponse,
    summary="Get collection knowledge entry details",
)
async def get_collection_knowledge_file(
    tenant_id: str, collection_id: str, file_id: str, db: Session = Depends(get_db)
):
    """Get specific collection knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        entry = await get_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            collection_id=collection_id,  # Collection level
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

        return KnowledgeEntryResponse.from_db_model(entry)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get collection knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve knowledge entry"
        )


@router.patch(
    "/{tenant_id}/{collection_id}/files/{file_id}",
    response_model=KnowledgeEntryResponse,
    summary="Update collection knowledge entry",
)
async def update_collection_knowledge_file(
    tenant_id: str, collection_id: str, file_id: str, request: KnowledgeEntryUpdate, db: Session = Depends(get_db)
):
    """Update collection knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        # Build updates dict from non-None fields
        updates: Dict[str, Any] = {}
        if request.status is not None:
            updates["status"] = request.status
        if request.knowledge_status is not None:
            updates["knowledge_status"] = request.knowledge_status
        if request.metadata is not None:
            updates["entry_metadata"] = request.metadata

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update")

        entry = await update_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            updates=updates,
            collection_id=collection_id,  # Collection level
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

        return KnowledgeEntryResponse.from_db_model(entry)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to update collection knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update knowledge entry"
        )


@router.delete(
    "/{tenant_id}/{collection_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete collection knowledge entry",
)
async def delete_collection_knowledge_file(
    tenant_id: str,
    collection_id: str,
    file_id: str,
    hard_delete: bool = Query(False, description="Permanently delete"),
    db: Session = Depends(get_db),
):
    """Delete collection knowledge entry."""
    try:
        # Validate file_id format
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id format. Must be a valid UUID."
            )

        success = await delete_knowledge_entry(
            db=db,
            tenant_id=tenant_id,
            file_id=file_id,
            collection_id=collection_id,  # Collection level
            hard_delete=hard_delete,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge entry not found for file_id {file_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to delete collection knowledge file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete knowledge entry"
        )
