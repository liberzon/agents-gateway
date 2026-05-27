import datetime
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from db.db_models import SupervisorRunDB

logger = logging.getLogger(__name__)


def create_supervisor_run(
    db: Session,
    team_id: str,
    user_message: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SupervisorRunDB:
    run = SupervisorRunDB(
        team_id=team_id,  # type: ignore[assignment]
        session_id=session_id,  # type: ignore[assignment]
        user_id=user_id,  # type: ignore[assignment]
        user_message=user_message,  # type: ignore[assignment]
        status="pending",  # type: ignore[assignment]
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(f"Created supervisor run {run.id} for team {team_id}")
    return run


def update_supervisor_run(
    db: Session,
    run_id: UUID,
    status: Optional[str] = None,
    supervisor_response: Optional[Dict[str, Any]] = None,
    worker_agent_id: Optional[str] = None,
    execution_engine: Optional[str] = None,
    execution_output: Optional[str] = None,
) -> bool:
    run = db.query(SupervisorRunDB).filter(SupervisorRunDB.id == run_id).first()
    if not run:
        return False

    if status:
        run.status = status  # type: ignore[assignment]
    if supervisor_response is not None:
        run.supervisor_response = supervisor_response  # type: ignore[assignment]
    if worker_agent_id:
        run.worker_agent_id = worker_agent_id  # type: ignore[assignment]
    if execution_engine:
        run.execution_engine = execution_engine  # type: ignore[assignment]
    if execution_output:
        run.execution_output = execution_output  # type: ignore[assignment]
    if status in ("completed", "failed"):
        run.completed_at = datetime.datetime.utcnow()  # type: ignore[assignment]

    db.commit()
    return True


def get_supervisor_run(db: Session, run_id: UUID) -> Optional[SupervisorRunDB]:
    return db.query(SupervisorRunDB).filter(SupervisorRunDB.id == run_id).first()


def list_supervisor_runs(
    db: Session,
    team_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[SupervisorRunDB]:
    return (
        db.query(SupervisorRunDB)
        .filter(SupervisorRunDB.team_id == team_id)
        .order_by(SupervisorRunDB.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
