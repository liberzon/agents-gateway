import datetime
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from db.db_models import ExecutionJobDB

logger = logging.getLogger(__name__)


def create_execution_job(
    db: Session,
    worker_config: Dict[str, Any],
    prompt: str,
    execution_target: Optional[Dict[str, Any]] = None,
    supervisor_run_id: Optional[UUID] = None,
    target_host: Optional[str] = None,
    memory_limit_mb: Optional[int] = None,
    timeout_minutes: int = 15,
) -> ExecutionJobDB:
    timeout_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
    job = ExecutionJobDB(
        worker_config=worker_config,  # type: ignore[assignment]
        prompt=prompt,  # type: ignore[assignment]
        execution_target=execution_target,  # type: ignore[assignment]
        supervisor_run_id=supervisor_run_id,  # type: ignore[assignment]
        target_host=target_host,  # type: ignore[assignment]
        memory_limit_mb=memory_limit_mb,  # type: ignore[assignment]
        timeout_at=timeout_at,  # type: ignore[assignment]
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created execution job {job.id}")
    return job


def get_execution_job(db: Session, job_id: UUID) -> Optional[ExecutionJobDB]:
    return db.query(ExecutionJobDB).filter(ExecutionJobDB.id == job_id).first()


def get_queued_jobs(db: Session, target_host: Optional[str] = None, limit: int = 10) -> List[ExecutionJobDB]:
    query = db.query(ExecutionJobDB).filter(ExecutionJobDB.status == "queued")
    if target_host:
        query = query.filter(ExecutionJobDB.target_host == target_host)
    return query.order_by(ExecutionJobDB.created_at.asc()).limit(limit).all()


def claim_job(db: Session, job_id: UUID) -> bool:
    job = get_execution_job(db, job_id)
    if not job or job.status != "queued":
        return False
    job.status = "running"  # type: ignore[assignment]
    job.started_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    logger.info(f"Claimed job {job_id}")
    return True


def complete_job(db: Session, job_id: UUID, result: Dict[str, Any]) -> bool:
    job = get_execution_job(db, job_id)
    if not job:
        return False
    job.status = "completed"  # type: ignore[assignment]
    job.result = result  # type: ignore[assignment]
    job.completed_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    logger.info(f"Completed job {job_id}")
    return True


def fail_job(db: Session, job_id: UUID, error: str, reason: str = "error") -> bool:
    job = get_execution_job(db, job_id)
    if not job:
        return False
    job.status = reason  # type: ignore[assignment]  # "failed", "oom", "failed_circuit_open"
    job.last_failure_reason = error  # type: ignore[assignment]
    job.completed_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    logger.info(f"Failed job {job_id}: {reason}")
    return True


def update_job_status(db: Session, job_id: UUID, status: str) -> bool:
    job = get_execution_job(db, job_id)
    if not job:
        return False
    job.status = status  # type: ignore[assignment]
    db.commit()
    return True


def increment_retry(db: Session, job_id: UUID, new_memory_limit_mb: int) -> bool:
    job = get_execution_job(db, job_id)
    if not job:
        return False
    job.retry_count = (job.retry_count or 0) + 1  # type: ignore[assignment]
    job.memory_limit_mb = new_memory_limit_mb  # type: ignore[assignment]
    job.status = "queued"  # type: ignore[assignment]
    job.started_at = None  # type: ignore[assignment]
    job.completed_at = None  # type: ignore[assignment]
    db.commit()
    logger.info(f"Retrying job {job_id} with {new_memory_limit_mb}MB (attempt {job.retry_count})")
    return True


def list_jobs_by_supervisor_run(db: Session, supervisor_run_id: UUID) -> List[ExecutionJobDB]:
    return (
        db.query(ExecutionJobDB)
        .filter(ExecutionJobDB.supervisor_run_id == supervisor_run_id)
        .order_by(ExecutionJobDB.created_at.asc())
        .all()
    )
