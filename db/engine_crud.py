"""CRUD operations for ExecutionEngine registry."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.db_models import ExecutionEngineDB

logger = logging.getLogger(__name__)


def create_engine(
    db: Session,
    engine_id: str,
    name: str,
    engine_type: str,
    provider: str = "anthropic",
    handler_config: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    is_default: bool = False,
) -> ExecutionEngineDB:
    engine = ExecutionEngineDB(
        id=engine_id,  # type: ignore[assignment]
        name=name,  # type: ignore[assignment]
        type=engine_type,  # type: ignore[assignment]
        provider=provider,  # type: ignore[assignment]
        handler_config=handler_config,  # type: ignore[assignment]
        description=description,  # type: ignore[assignment]
        is_default=is_default,  # type: ignore[assignment]
    )
    db.add(engine)
    db.commit()
    db.refresh(engine)
    return engine


def get_engine(db: Session, engine_id: str) -> Optional[ExecutionEngineDB]:
    return (
        db.query(ExecutionEngineDB)
        .filter(ExecutionEngineDB.id == engine_id, ExecutionEngineDB.is_active.is_(True))
        .first()
    )


def get_all_engines(db: Session, include_inactive: bool = False) -> List[ExecutionEngineDB]:
    query = db.query(ExecutionEngineDB)
    if not include_inactive:
        query = query.filter(ExecutionEngineDB.is_active.is_(True))
    return query.all()


def get_default_engine(db: Session) -> Optional[ExecutionEngineDB]:
    return (
        db.query(ExecutionEngineDB)
        .filter(ExecutionEngineDB.is_default.is_(True), ExecutionEngineDB.is_active.is_(True))
        .first()
    )


def update_engine(db: Session, engine_id: str, **kwargs: Any) -> Optional[ExecutionEngineDB]:
    engine = get_engine(db, engine_id)
    if not engine:
        return None
    for key, value in kwargs.items():
        if hasattr(engine, key) and value is not None:
            setattr(engine, key, value)
    db.commit()
    db.refresh(engine)
    return engine


def soft_delete_engine(db: Session, engine_id: str) -> bool:
    engine = get_engine(db, engine_id)
    if not engine:
        return False
    engine.is_active = False  # type: ignore[assignment]
    db.commit()
    return True
