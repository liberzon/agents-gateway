import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from supervisor.models import ApprovalDecision, ExecutionResult, JobStatus
from supervisor.queue.crud import (
    complete_job,
    create_execution_job,
    fail_job,
    get_execution_job,
    update_job_status,
)

logger = logging.getLogger(__name__)


class JobProducer:
    """Submits execution jobs to the queue and tracks their status."""

    def __init__(self, db: Session):
        self.db = db

    def submit_job(
        self,
        worker_config: Dict[str, Any],
        prompt: str,
        execution_target: Optional[Dict[str, Any]] = None,
        supervisor_run_id: Optional[UUID] = None,
        target_host: Optional[str] = None,
        memory_limit_mb: Optional[int] = None,
        timeout_minutes: int = 15,
    ) -> UUID:
        job = create_execution_job(
            db=self.db,
            worker_config=worker_config,
            prompt=prompt,
            execution_target=execution_target,
            supervisor_run_id=supervisor_run_id,
            target_host=target_host,
            memory_limit_mb=memory_limit_mb,
            timeout_minutes=timeout_minutes,
        )
        return job.id  # type: ignore[return-value]

    def get_job_status(self, job_id: UUID) -> Optional[JobStatus]:
        job = get_execution_job(self.db, job_id)
        if not job:
            return None
        return JobStatus(job.status)

    def get_job_result(self, job_id: UUID) -> Optional[ExecutionResult]:
        job = get_execution_job(self.db, job_id)
        if not job or not job.result:
            return None
        return ExecutionResult(**job.result)

    def cancel_job(self, job_id: UUID) -> bool:
        return update_job_status(self.db, job_id, "failed")

    async def await_job(
        self, job_id: UUID, timeout: float = 900.0, poll_interval: float = 1.0
    ) -> Optional[ExecutionResult]:
        """Poll the job until it completes or times out."""
        elapsed = 0.0
        while elapsed < timeout:
            status = self.get_job_status(job_id)
            if status is None:
                return None
            if status in (JobStatus.completed, JobStatus.failed, JobStatus.oom, JobStatus.failed_circuit_open):
                return self.get_job_result(job_id)
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        logger.warning(f"Job {job_id} timed out after {timeout}s")
        fail_job(self.db, job_id, "Timed out waiting for result", "failed")
        return None

    def submit_approval(self, job_id: UUID, decision: ApprovalDecision) -> bool:
        job = get_execution_job(self.db, job_id)
        if not job or job.status != "awaiting_approval":
            return False
        # Store decision in result field temporarily for consumer to pick up
        current_result = dict(job.result) if job.result else {}
        current_result["_approval_decision"] = decision.model_dump()
        complete_job(self.db, job_id, current_result)
        # Reset status to running so consumer can continue
        update_job_status(self.db, job_id, "running")
        return True
