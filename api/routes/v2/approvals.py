"""Approval endpoints for satellite agent HITL flows.

These endpoints allow external channels (Telegram, Slack, UI, webhook)
to poll for pending approvals and submit approval decisions.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from supervisor.approval import (
    get_pending_approval,
    get_pending_approvals,
    list_plugins,
    submit_decision,
)

logger = logging.getLogger(__name__)

v2_approvals_router = APIRouter(prefix="/approvals", tags=["V2 Approvals"])


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    reason: str = ""
    modified_args: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    job_id: str
    worker_name: str
    tool_name: str
    tool_args: Dict[str, Any] = {}
    risk_level: str = "medium"
    reason: str = ""
    timestamp: str = ""


class DecisionResponse(BaseModel):
    job_id: str
    status: str
    message: str


@v2_approvals_router.get("", response_model=List[ApprovalResponse])
async def list_pending_approvals() -> List[ApprovalResponse]:
    """List all pending approval requests. Use this for polling-based approval flows."""
    pending = get_pending_approvals()
    return [
        ApprovalResponse(
            job_id=n.job_id,
            worker_name=n.worker_name,
            tool_name=n.tool_name,
            tool_args=n.tool_args,
            risk_level=n.risk_level,
            reason=n.reason,
            timestamp=n.timestamp.isoformat(),
        )
        for n in pending
    ]


@v2_approvals_router.get("/{job_id}", response_model=ApprovalResponse)
async def get_approval(job_id: str) -> ApprovalResponse:
    """Get a specific pending approval request."""
    notification = get_pending_approval(job_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pending approval for job {job_id}")
    return ApprovalResponse(
        job_id=notification.job_id,
        worker_name=notification.worker_name,
        tool_name=notification.tool_name,
        tool_args=notification.tool_args,
        risk_level=notification.risk_level,
        reason=notification.reason,
        timestamp=notification.timestamp.isoformat(),
    )


@v2_approvals_router.post("/{job_id}/decide", response_model=DecisionResponse)
async def decide_approval(job_id: str, body: ApprovalDecisionRequest) -> DecisionResponse:
    """Submit an approval decision (approve or deny)."""
    success = submit_decision(
        job_id=job_id,
        approved=body.approved,
        reason=body.reason,
        modified_args=body.modified_args,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pending approval for job {job_id}")

    action = "approved" if body.approved else "denied"
    return DecisionResponse(job_id=job_id, status=action, message=f"Tool call {action}")


@v2_approvals_router.post("/{job_id}/approve", response_model=DecisionResponse)
async def approve(job_id: str) -> DecisionResponse:
    """Quick approve — shortcut for decide with approved=true."""
    success = submit_decision(job_id=job_id, approved=True, reason="Approved via API")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pending approval for job {job_id}")
    return DecisionResponse(job_id=job_id, status="approved", message="Tool call approved")


@v2_approvals_router.post("/{job_id}/deny", response_model=DecisionResponse)
async def deny(job_id: str) -> DecisionResponse:
    """Quick deny — shortcut for decide with approved=false."""
    success = submit_decision(job_id=job_id, approved=False, reason="Denied via API")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No pending approval for job {job_id}")
    return DecisionResponse(job_id=job_id, status="denied", message="Tool call denied")


@v2_approvals_router.get("/plugins/list", response_model=List[str])
async def get_notification_plugins() -> List[str]:
    """List available notification plugins for approval routing."""
    return list_plugins()
