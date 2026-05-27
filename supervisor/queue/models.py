from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from supervisor.models import ApprovalRequest, ExecutionResult, JobStatus, WorkerConfig


class Job(BaseModel):
    id: UUID
    supervisor_run_id: Optional[UUID] = None
    worker_config: WorkerConfig
    prompt: str
    execution_target: Optional[Dict[str, Any]] = None
    status: JobStatus = JobStatus.queued
    result: Optional[ExecutionResult] = None
    container_id: Optional[str] = None
    target_host: Optional[str] = None
    retry_count: int = 0
    memory_limit_mb: Optional[int] = None
    last_failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None


class JobSubmission(BaseModel):
    worker_config: WorkerConfig
    prompt: str
    execution_target: Optional[Dict[str, Any]] = None
    supervisor_run_id: Optional[UUID] = None
    target_host: Optional[str] = None
    memory_limit_mb: Optional[int] = None
    timeout_minutes: int = 15


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    retry_count: int = 0
    container_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PendingApproval(BaseModel):
    job_id: UUID
    approval_request: ApprovalRequest
    created_at: datetime = Field(default_factory=datetime.utcnow)
