import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.target_crud import create_target, get_all_targets, get_target, soft_delete_target, update_target

logger = logging.getLogger(__name__)

v2_targets_router = APIRouter(prefix="/targets", tags=["V2 Targets"])


class TargetCreateRequest(BaseModel):
    id: str
    name: str
    type: str  # local, ssh, remote_service, managed_agents
    connection_config: Dict[str, Any] = {}
    capacity: Dict[str, Any] = {}
    worker_pool: str = "linux_worker_pool"


class TargetResponse(BaseModel):
    id: str
    name: str
    type: str
    connection_config: Dict[str, Any] = {}
    capacity: Dict[str, Any] = {}
    worker_pool: str = "linux_worker_pool"
    is_active: bool = True


@v2_targets_router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target_v2(body: TargetCreateRequest, db: Session = Depends(get_db)) -> TargetResponse:
    existing = get_target(db, body.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Target {body.id} already exists")
    target = create_target(db, body.id, body.name, body.type, body.connection_config, body.capacity, body.worker_pool)
    return TargetResponse(
        id=str(target.id),
        name=str(target.name),
        type=str(target.type),
        connection_config=target.connection_config or {},  # type: ignore[arg-type]
        capacity=target.capacity or {},  # type: ignore[arg-type]
        worker_pool=str(target.worker_pool),
        is_active=bool(target.is_active),
    )


@v2_targets_router.get("", response_model=List[TargetResponse])
async def list_targets_v2(db: Session = Depends(get_db)) -> List[TargetResponse]:
    targets = get_all_targets(db)
    return [
        TargetResponse(
            id=str(t.id),
            name=str(t.name),
            type=str(t.type),
            connection_config=t.connection_config or {},  # type: ignore[arg-type]
            capacity=t.capacity or {},  # type: ignore[arg-type]
            worker_pool=str(t.worker_pool),
            is_active=bool(t.is_active),
        )
        for t in targets
    ]


@v2_targets_router.get("/{target_id}", response_model=TargetResponse)
async def get_target_v2(target_id: str, db: Session = Depends(get_db)) -> TargetResponse:
    target = get_target(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    return TargetResponse(
        id=str(target.id),
        name=str(target.name),
        type=str(target.type),
        connection_config=target.connection_config or {},  # type: ignore[arg-type]
        capacity=target.capacity or {},  # type: ignore[arg-type]
        worker_pool=str(target.worker_pool),
        is_active=bool(target.is_active),
    )


@v2_targets_router.put("/{target_id}", response_model=TargetResponse)
async def update_target_v2(target_id: str, body: TargetCreateRequest, db: Session = Depends(get_db)) -> TargetResponse:
    target = update_target(
        db,
        target_id,
        name=body.name,
        type=body.type,
        connection_config=body.connection_config,
        capacity=body.capacity,
        worker_pool=body.worker_pool,
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    return TargetResponse(
        id=str(target.id),
        name=str(target.name),
        type=str(target.type),
        connection_config=target.connection_config or {},  # type: ignore[arg-type]
        capacity=target.capacity or {},  # type: ignore[arg-type]
        worker_pool=str(target.worker_pool),
        is_active=bool(target.is_active),
    )


@v2_targets_router.delete("/{target_id}")
async def delete_target_v2(target_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    if not soft_delete_target(db, target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    return {"id": target_id, "message": "Target deleted"}


@v2_targets_router.get("/{target_id}/health")
async def target_health_v2(target_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    target = get_target(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    # Health check depends on target type — placeholder
    return {
        "target_id": target_id,
        "status": "unknown",
        "message": "Health check not yet implemented for this target type",
    }
