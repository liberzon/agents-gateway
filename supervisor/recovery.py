import logging
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from supervisor.models import RetryPolicy
from supervisor.queue.crud import fail_job, get_execution_job, increment_retry

logger = logging.getLogger(__name__)


class RetryAction(str, Enum):
    retry = "retry"
    replan = "replan"
    circuit_open = "circuit_open"


def handle_oom(
    db: Session,
    job_id: UUID,
    retry_policy: Optional[RetryPolicy] = None,
) -> RetryAction:
    """Handle OOM failure with retry escalation and circuit breaker.

    1. If under max_retries: retry with memory_multiplier * current_memory
    2. If at limit + replan enabled: return replan for supervisor re-classification
    3. If circuit breaker threshold hit: mark failed_circuit_open, escalate to human
    """
    policy = retry_policy or RetryPolicy()
    job = get_execution_job(db, job_id)
    if not job:
        logger.error(f"Job {job_id} not found for OOM handling")
        return RetryAction.circuit_open

    current_retries = job.retry_count or 0
    current_memory = job.memory_limit_mb or 4096
    total_failures = current_retries + 1  # including this OOM

    # Circuit breaker check
    if total_failures >= policy.circuit_breaker_threshold:
        fail_job(db, job_id, f"Circuit breaker open after {total_failures} failures", "failed_circuit_open")
        logger.warning(f"Circuit breaker open for job {job_id} after {total_failures} failures")
        return RetryAction.circuit_open

    # Retry with higher memory
    if current_retries < policy.max_retries:
        new_memory = int(current_memory * policy.memory_multiplier)
        increment_retry(db, job_id, new_memory)
        logger.info(f"OOM retry for job {job_id}: {current_memory}MB -> {new_memory}MB (attempt {current_retries + 1})")
        return RetryAction.retry

    # Supervisor re-plan
    if policy.enable_supervisor_replan:
        fail_job(db, job_id, "OOM after max retries, needs supervisor re-planning", "oom")
        logger.info(f"Job {job_id} needs supervisor re-plan after {current_retries} retries")
        return RetryAction.replan

    # Fallback: circuit open
    fail_job(db, job_id, f"OOM after {current_retries} retries, no replan configured", "failed_circuit_open")
    return RetryAction.circuit_open


def should_retry(db: Session, job_id: UUID, retry_policy: Optional[RetryPolicy] = None) -> bool:
    """Check if a failed job should be retried."""
    policy = retry_policy or RetryPolicy()
    job = get_execution_job(db, job_id)
    if not job:
        return False
    return int(job.retry_count or 0) < policy.max_retries


def is_oom_exit(exit_code: Optional[int] = None, k8s_reason: Optional[str] = None) -> bool:
    """Detect OOM from container exit code or K8s status."""
    if exit_code is not None and int(exit_code) == 137:  # Docker SIGKILL (OOM)
        return True
    if k8s_reason and k8s_reason.lower() == "oomkilled":
        return True
    return False
