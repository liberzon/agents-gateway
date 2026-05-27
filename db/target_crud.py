"""CRUD operations for ExecutionTarget registry."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.db_models import ExecutionTargetDB

logger = logging.getLogger(__name__)


def create_target(
    db: Session,
    target_id: str,
    name: str,
    target_type: str,
    connection_config: Optional[Dict[str, Any]] = None,
    capacity: Optional[Dict[str, Any]] = None,
    worker_pool: str = "linux_worker_pool",
) -> ExecutionTargetDB:
    target = ExecutionTargetDB(
        id=target_id,  # type: ignore[assignment]
        name=name,  # type: ignore[assignment]
        type=target_type,  # type: ignore[assignment]
        connection_config=connection_config,  # type: ignore[assignment]
        capacity=capacity,  # type: ignore[assignment]
        worker_pool=worker_pool,  # type: ignore[assignment]
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def get_target(db: Session, target_id: str) -> Optional[ExecutionTargetDB]:
    return (
        db.query(ExecutionTargetDB)
        .filter(ExecutionTargetDB.id == target_id, ExecutionTargetDB.is_active.is_(True))
        .first()
    )


def get_all_targets(db: Session, include_inactive: bool = False) -> List[ExecutionTargetDB]:
    query = db.query(ExecutionTargetDB)
    if not include_inactive:
        query = query.filter(ExecutionTargetDB.is_active.is_(True))
    return query.all()


def get_targets_by_pool(db: Session, worker_pool: str) -> List[ExecutionTargetDB]:
    return (
        db.query(ExecutionTargetDB)
        .filter(ExecutionTargetDB.worker_pool == worker_pool, ExecutionTargetDB.is_active.is_(True))
        .all()
    )


def update_target(db: Session, target_id: str, **kwargs: Any) -> Optional[ExecutionTargetDB]:
    target = get_target(db, target_id)
    if not target:
        return None
    for key, value in kwargs.items():
        if hasattr(target, key) and value is not None:
            setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


def soft_delete_target(db: Session, target_id: str) -> bool:
    target = get_target(db, target_id)
    if not target:
        return False
    target.is_active = False  # type: ignore[assignment]
    db.commit()
    return True
