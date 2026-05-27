import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.engine_crud import create_engine, get_all_engines, get_engine, soft_delete_engine, update_engine
from db.session import get_db

logger = logging.getLogger(__name__)

v2_engines_router = APIRouter(prefix="/engines", tags=["V2 Engines"])


class EngineCreateRequest(BaseModel):
    id: str
    name: str
    type: str  # code_agent, managed_agent, direct_ops, custom
    provider: str = "anthropic"
    handler_config: Dict[str, Any] = {}
    description: Optional[str] = None
    is_default: bool = False


class EngineResponse(BaseModel):
    id: str
    name: str
    type: str
    provider: str
    handler_config: Dict[str, Any] = {}
    description: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


@v2_engines_router.post("", response_model=EngineResponse, status_code=status.HTTP_201_CREATED)
async def create_engine_v2(body: EngineCreateRequest, db: Session = Depends(get_db)) -> EngineResponse:
    existing = get_engine(db, body.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Engine {body.id} already exists")
    engine = create_engine(
        db, body.id, body.name, body.type, body.provider, body.handler_config, body.description, body.is_default
    )
    return EngineResponse(
        id=str(engine.id),
        name=str(engine.name),
        type=str(engine.type),
        provider=str(engine.provider),
        handler_config=engine.handler_config or {},  # type: ignore[arg-type]
        description=engine.description,  # type: ignore[arg-type]
        is_default=bool(engine.is_default),
        is_active=bool(engine.is_active),
    )


@v2_engines_router.get("", response_model=List[EngineResponse])
async def list_engines_v2(db: Session = Depends(get_db)) -> List[EngineResponse]:
    engines = get_all_engines(db)
    return [
        EngineResponse(
            id=str(e.id),
            name=str(e.name),
            type=str(e.type),
            provider=str(e.provider),
            handler_config=e.handler_config or {},  # type: ignore[arg-type]
            description=e.description,  # type: ignore[arg-type]
            is_default=bool(e.is_default),
            is_active=bool(e.is_active),
        )
        for e in engines
    ]


@v2_engines_router.get("/{engine_id}", response_model=EngineResponse)
async def get_engine_v2(engine_id: str, db: Session = Depends(get_db)) -> EngineResponse:
    engine = get_engine(db, engine_id)
    if not engine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Engine {engine_id} not found")
    return EngineResponse(
        id=str(engine.id),
        name=str(engine.name),
        type=str(engine.type),
        provider=str(engine.provider),
        handler_config=engine.handler_config or {},  # type: ignore[arg-type]
        description=engine.description,  # type: ignore[arg-type]
        is_default=bool(engine.is_default),
        is_active=bool(engine.is_active),
    )


@v2_engines_router.put("/{engine_id}", response_model=EngineResponse)
async def update_engine_v2(engine_id: str, body: EngineCreateRequest, db: Session = Depends(get_db)) -> EngineResponse:
    engine = update_engine(
        db,
        engine_id,
        name=body.name,
        type=body.type,
        provider=body.provider,
        handler_config=body.handler_config,
        description=body.description,
        is_default=body.is_default,
    )
    if not engine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Engine {engine_id} not found")
    return EngineResponse(
        id=str(engine.id),
        name=str(engine.name),
        type=str(engine.type),
        provider=str(engine.provider),
        handler_config=engine.handler_config or {},  # type: ignore[arg-type]
        description=engine.description,  # type: ignore[arg-type]
        is_default=bool(engine.is_default),
        is_active=bool(engine.is_active),
    )


@v2_engines_router.delete("/{engine_id}")
async def delete_engine_v2(engine_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    if not soft_delete_engine(db, engine_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Engine {engine_id} not found")
    return {"id": engine_id, "message": "Engine deleted"}
