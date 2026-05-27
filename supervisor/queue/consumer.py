import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from supervisor.models import ApprovalDecision, ApprovalRequest
from supervisor.queue.crud import (
    claim_job,
    complete_job,
    fail_job,
    get_execution_job,
    get_queued_jobs,
    update_job_status,
)

logger = logging.getLogger(__name__)


class JobConsumer:
    """Pulls and processes execution jobs from the queue. Runs on remote agent service."""

    def __init__(self, db: Session, target_host: Optional[str] = None):
        self.db = db
        self.target_host = target_host

    def poll_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        jobs = get_queued_jobs(self.db, target_host=self.target_host, limit=limit)
        return [
            {
                "id": str(job.id),
                "worker_config": job.worker_config,
                "prompt": job.prompt,
                "execution_target": job.execution_target,
                "memory_limit_mb": job.memory_limit_mb,
                "timeout_at": str(job.timeout_at) if job.timeout_at else None,
            }
            for job in jobs
        ]

    def claim(self, job_id: UUID) -> bool:
        return claim_job(self.db, job_id)

    def complete(self, job_id: UUID, result: Dict[str, Any]) -> bool:
        return complete_job(self.db, job_id, result)

    def fail(self, job_id: UUID, error: str, reason: str = "failed") -> bool:
        return fail_job(self.db, job_id, error, reason)

    def request_approval(self, job_id: UUID, approval_request: ApprovalRequest) -> bool:
        job = get_execution_job(self.db, job_id)
        if not job:
            return False
        # Store approval request in result and change status
        current_result = dict(job.result) if job.result else {}
        current_result["_pending_approval"] = approval_request.model_dump()
        job.result = current_result  # type: ignore[assignment]
        update_job_status(self.db, job_id, "awaiting_approval")
        self.db.commit()
        logger.info(f"Job {job_id} awaiting approval for {approval_request.tool_name}")
        return True

    def poll_approval(self, job_id: UUID) -> Optional[ApprovalDecision]:
        job = get_execution_job(self.db, job_id)
        if not job or not job.result:
            return None
        result = dict(job.result)
        decision_data = result.get("_approval_decision")
        if decision_data:
            # Clear the decision from result
            result.pop("_approval_decision", None)
            result.pop("_pending_approval", None)
            job.result = result  # type: ignore[assignment]
            self.db.commit()
            return ApprovalDecision(**decision_data)
        return None
