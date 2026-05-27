import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.services.auth import verify_admin_secret
from cache.background_tasks import background_task_manager
from cache.prompts_cache import (
    get_cache_status,
    invalidate_prompt_cache,
    load_all_prompts_to_cache,
    prompt_cache,
    refresh_all_prompts,
)
from db.api_key_crud import (
    api_key_to_dict,
    create_api_key,
    deactivate_api_key,
    delete_api_key,
    get_all_api_keys,
    get_api_key_by_id,
    get_api_keys_by_owner,
    update_api_key,
)
from db.session import get_db

# Create admin router with admin secret authentication
# All admin routes require X-Admin-Secret header (unless AUTH_DISABLED=true)
admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_secret)])


# =============================================================================
# API Key Management Models
# =============================================================================


class CreateApiKeyRequest(BaseModel):
    """Request model for creating an API key."""

    name: str = Field(..., description="Human-readable name for the API key")
    owner_id: Optional[str] = Field(None, description="Owner identifier")
    scopes: Optional[List[str]] = Field(None, description="List of allowed scopes")
    rate_limit: int = Field(1000, description="Max requests per hour (0 = unlimited)")
    expires_in_days: Optional[int] = Field(None, description="Days until expiration (None = never)")


class CreateApiKeyResponse(BaseModel):
    """Response model for creating an API key."""

    id: int
    name: str
    api_key: str = Field(..., description="The raw API key (only shown once)")
    owner_id: Optional[str]
    scopes: Optional[List[str]]
    rate_limit: int
    expires_at: Optional[str]
    created_at: str


class UpdateApiKeyRequest(BaseModel):
    """Request model for updating an API key."""

    name: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit: Optional[int] = None
    expires_in_days: Optional[int] = None
    is_active: Optional[bool] = None


@admin_router.get("/cache/stats")
async def get_cache_stats():
    """
    Get statistics about the cache usage.

    Returns:
        dict: Cache statistics
    """
    logging.info("Request for cache statistics")

    return {
        "prompt_cache": {
            "size": len(prompt_cache),
            "maxsize": prompt_cache.maxsize,
            "ttl": prompt_cache.ttl,
            "currsize": len(prompt_cache),
        }
    }


@admin_router.post("/cache/invalidate/prompts")
async def invalidate_prompts_cache(prompt_id: Optional[str] = None):
    """
    Invalidate prompt cache for a specific prompt or all prompts.

    Args:
        prompt_id: If provided, only invalidate cache for this prompt

    Returns:
        dict: Status message
    """
    invalidate_prompt_cache(prompt_id)

    if prompt_id:
        logging.info(f"Invalidated prompt cache for prompt: {prompt_id}")
        message = f"Prompt cache invalidated for {prompt_id}"
    else:
        logging.info("Invalidated all prompt caches")
        message = "All prompt caches invalidated"

    return {"status": "success", "message": message}


@admin_router.get("/cache/status")
async def get_cache_status_endpoint():
    """
    Get detailed cache status including initialization state and statistics.

    Returns:
        dict: Detailed cache status information
    """
    logging.info("Request for detailed cache status")

    try:
        status_info = get_cache_status()
        logging.debug(f"Cache status retrieved: {status_info}")
        return status_info
    except Exception as e:
        logging.error(f"Error retrieving cache status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve cache status")


@admin_router.post("/cache/reload")
async def reload_cache():
    """
    Trigger a full cache reload manually.

    Returns:
        dict: Status message
    """
    logging.info("Manual cache reload requested")

    try:
        # Trigger cache reload in background
        import asyncio

        asyncio.create_task(load_all_prompts_to_cache())

        # Don't wait for completion, return immediately
        return {"status": "success", "message": "Cache reload initiated in background"}
    except Exception as e:
        logging.error(f"Error initiating cache reload: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initiate cache reload")


@admin_router.post("/cache/refresh")
async def refresh_cache():
    """
    Trigger a full cache refresh manually.

    Returns:
        dict: Status message
    """
    logging.info("Manual cache refresh requested")

    try:
        # Trigger cache refresh in background
        import asyncio

        asyncio.create_task(refresh_all_prompts())

        # Don't wait for completion, return immediately
        return {"status": "success", "message": "Cache refresh initiated in background"}
    except Exception as e:
        logging.error(f"Error initiating cache refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initiate cache refresh"
        )


@admin_router.get("/background-tasks")
async def get_background_tasks_status():
    """
    Get status of all background tasks.

    Returns:
        dict: Background tasks status information
    """
    logging.info("Request for background tasks status")

    try:
        task_status = background_task_manager.get_all_task_status()
        logging.debug(f"Background tasks status: {list(task_status.keys())}")
        return {
            "tasks": task_status,
            "total_tasks": len(task_status),
        }
    except Exception as e:
        logging.error(f"Error retrieving background tasks status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve background tasks status"
        )


@admin_router.post("/background-tasks/{task_name}/cancel")
async def cancel_background_task(task_name: str):
    """
    Cancel a specific background task.

    Args:
        task_name: Name of the task to cancel

    Returns:
        dict: Status message
    """
    logging.info(f"Request to cancel background task: {task_name}")

    try:
        success = await background_task_manager.cancel_task(task_name)

        if success:
            return {"status": "success", "message": f"Task '{task_name}' cancelled successfully"}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error cancelling task '{task_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel task '{task_name}'"
        )


# =============================================================================
# API Key Management Endpoints
# =============================================================================


@admin_router.post("/api-keys", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(request: CreateApiKeyRequest, db=Depends(get_db)):
    """
    Create a new API key.

    IMPORTANT: The raw API key is only returned once at creation time.
    Store it securely - it cannot be retrieved later.

    Args:
        request: API key creation parameters

    Returns:
        CreateApiKeyResponse with the raw API key
    """
    logging.info(f"Creating API key: name={request.name}, owner={request.owner_id}")

    try:
        # Calculate expiration if specified
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=request.expires_in_days)

        api_key_record, raw_key = create_api_key(
            db=db,
            name=request.name,
            owner_id=request.owner_id,
            scopes=request.scopes,
            rate_limit=request.rate_limit,
            expires_at=expires_at,
        )

        return CreateApiKeyResponse(
            id=api_key_record.id,  # type: ignore[arg-type]
            name=api_key_record.name,  # type: ignore[arg-type]
            api_key=raw_key,
            owner_id=api_key_record.owner_id,  # type: ignore[arg-type]
            scopes=request.scopes,
            rate_limit=api_key_record.rate_limit,  # type: ignore[arg-type]
            expires_at=api_key_record.expires_at.isoformat() if api_key_record.expires_at else None,
            created_at=api_key_record.created_at.isoformat(),  # type: ignore[union-attr]
        )
    except Exception as e:
        logging.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create API key")


@admin_router.get("/api-keys")
async def list_api_keys(owner_id: Optional[str] = None, include_inactive: bool = False, db=Depends(get_db)):
    """
    List all API keys, optionally filtered by owner.

    Args:
        owner_id: Filter by owner (optional)
        include_inactive: Include deactivated keys (default: False)

    Returns:
        List of API key metadata (excluding the actual keys)
    """
    logging.info(f"Listing API keys: owner_id={owner_id}, include_inactive={include_inactive}")

    try:
        if owner_id:
            api_keys = get_api_keys_by_owner(db, owner_id, include_inactive)
        else:
            api_keys = get_all_api_keys(db, include_inactive)

        return {"api_keys": [api_key_to_dict(k) for k in api_keys], "total": len(api_keys)}
    except Exception as e:
        logging.error(f"Error listing API keys: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list API keys")


@admin_router.get("/api-keys/{key_id}")
async def get_api_key_endpoint(key_id: int, db=Depends(get_db)):
    """
    Get details of a specific API key by ID.

    Args:
        key_id: API key ID

    Returns:
        API key metadata (excluding the actual key)
    """
    logging.info(f"Getting API key: id={key_id}")

    api_key_record = get_api_key_by_id(db, key_id)
    if not api_key_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key {key_id} not found")

    return api_key_to_dict(api_key_record)


@admin_router.patch("/api-keys/{key_id}")
async def update_api_key_endpoint(key_id: int, request: UpdateApiKeyRequest, db=Depends(get_db)):
    """
    Update an API key's metadata.

    Args:
        key_id: API key ID
        request: Fields to update

    Returns:
        Updated API key metadata
    """
    logging.info(f"Updating API key: id={key_id}")

    try:
        # Calculate new expiration if specified
        expires_at = None
        if request.expires_in_days is not None:
            if request.expires_in_days > 0:
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=request.expires_in_days)
            # expires_in_days=0 means no expiration (None)

        api_key_record = update_api_key(
            db=db,
            key_id=key_id,
            name=request.name,
            scopes=request.scopes,
            rate_limit=request.rate_limit,
            expires_at=expires_at if request.expires_in_days is not None else None,
            is_active=request.is_active,
        )

        if not api_key_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key {key_id} not found")

        return api_key_to_dict(api_key_record)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating API key: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update API key")


@admin_router.delete("/api-keys/{key_id}")
async def delete_api_key_endpoint(key_id: int, permanent: bool = False, db=Depends(get_db)):
    """
    Delete an API key.

    Args:
        key_id: API key ID
        permanent: If True, permanently delete; otherwise soft delete (default: False)

    Returns:
        Status message
    """
    logging.info(f"Deleting API key: id={key_id}, permanent={permanent}")

    try:
        if permanent:
            success = delete_api_key(db, key_id)
            action = "permanently deleted"
        else:
            success = deactivate_api_key(db, key_id)
            action = "deactivated"

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key {key_id} not found")

        return {"status": "success", "message": f"API key {key_id} {action}"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting API key: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete API key")
