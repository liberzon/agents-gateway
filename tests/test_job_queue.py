"""Tests for job queue producer and consumer."""

import asyncio
import datetime
import unittest
import uuid
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from supervisor.models import ApprovalDecision, ApprovalRequest, JobStatus
from supervisor.queue.consumer import JobConsumer
from supervisor.queue.producer import JobProducer


def _make_job_db(
    status: str = "queued",
    result: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
    memory_limit_mb: Optional[int] = None,
) -> MagicMock:
    """Create a mock ExecutionJobDB row."""
    job = MagicMock()
    job.id = uuid.uuid4()
    job.status = status
    job.result = result
    job.retry_count = retry_count
    job.memory_limit_mb = memory_limit_mb
    job.worker_config = {"mcp_servers": []}
    job.prompt = "Fix bug"
    job.execution_target = None
    job.target_host = None
    job.timeout_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    job.created_at = datetime.datetime.utcnow()
    job.started_at = None
    job.completed_at = None
    job.last_failure_reason = None
    return job


# ---------------------------------------------------------------------------
# Producer tests
# ---------------------------------------------------------------------------


class TestJobProducerSubmit(unittest.TestCase):
    """Test submitting and tracking jobs."""

    def setUp(self) -> None:
        self.db = MagicMock()

    @patch("supervisor.queue.producer.create_execution_job")
    def test_submit_job_returns_uuid(self, mock_create: MagicMock) -> None:
        """Submit a job and verify a UUID is returned."""
        expected_id = uuid.uuid4()
        mock_job = MagicMock()
        mock_job.id = expected_id
        mock_create.return_value = mock_job

        producer = JobProducer(db=self.db)
        job_id = producer.submit_job(worker_config={"mcp_servers": []}, prompt="Do work")

        self.assertEqual(job_id, expected_id)
        mock_create.assert_called_once()

    @patch("supervisor.queue.producer.get_execution_job")
    def test_status_queued(self, mock_get: MagicMock) -> None:
        """Newly submitted job has status 'queued'."""
        mock_get.return_value = _make_job_db(status="queued")

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())

        self.assertEqual(status, JobStatus.queued)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_status_running(self, mock_get: MagicMock) -> None:
        """Job transitions to 'running'."""
        mock_get.return_value = _make_job_db(status="running")

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())

        self.assertEqual(status, JobStatus.running)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_status_completed(self, mock_get: MagicMock) -> None:
        """Job transitions to 'completed' with result."""
        mock_get.return_value = _make_job_db(status="completed", result={"output": "Done", "status": "completed"})

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())
        self.assertEqual(status, JobStatus.completed)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_status_failed(self, mock_get: MagicMock) -> None:
        """Job transitions to 'failed'."""
        mock_get.return_value = _make_job_db(status="failed")

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())
        self.assertEqual(status, JobStatus.failed)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_status_oom(self, mock_get: MagicMock) -> None:
        """Job transitions to 'oom' after OOM failure."""
        mock_get.return_value = _make_job_db(status="oom")

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())
        self.assertEqual(status, JobStatus.oom)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_get_result_returns_execution_result(self, mock_get: MagicMock) -> None:
        """Get result returns ExecutionResult for completed job."""
        mock_get.return_value = _make_job_db(
            status="completed",
            result={"output": "Task done", "status": "completed", "files_changed": ["a.py"]},
        )

        producer = JobProducer(db=self.db)
        result = producer.get_job_result(uuid.uuid4())
        self.assertIsNotNone(result)
        self.assertEqual(result.output, "Task done")  # type: ignore[union-attr]

    @patch("supervisor.queue.producer.get_execution_job")
    def test_get_result_returns_none_when_no_result(self, mock_get: MagicMock) -> None:
        """Get result returns None for queued job."""
        mock_get.return_value = _make_job_db(status="queued", result=None)

        producer = JobProducer(db=self.db)
        result = producer.get_job_result(uuid.uuid4())
        self.assertIsNone(result)

    @patch("supervisor.queue.producer.update_job_status")
    def test_cancel_job(self, mock_update: MagicMock) -> None:
        """Cancel a job sets status to failed."""
        mock_update.return_value = True

        producer = JobProducer(db=self.db)
        result = producer.cancel_job(uuid.uuid4())
        self.assertTrue(result)
        mock_update.assert_called_once()

    @patch("supervisor.queue.producer.fail_job")
    @patch("supervisor.queue.producer.get_execution_job")
    def test_await_job_timeout(self, mock_get: MagicMock, mock_fail: MagicMock) -> None:
        """Await job times out after specified duration."""
        mock_get.return_value = _make_job_db(status="running")

        producer = JobProducer(db=self.db)
        result = asyncio.run(producer.await_job(uuid.uuid4(), timeout=0.1, poll_interval=0.05))
        self.assertIsNone(result)
        mock_fail.assert_called_once()

    @patch("supervisor.queue.producer.get_execution_job")
    def test_await_job_completed(self, mock_get: MagicMock) -> None:
        """Await job returns result when completed."""
        job = _make_job_db(
            status="completed",
            result={"output": "Done", "status": "completed"},
        )
        mock_get.return_value = job

        producer = JobProducer(db=self.db)
        result = asyncio.run(producer.await_job(job.id, timeout=1.0, poll_interval=0.05))
        self.assertIsNotNone(result)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_get_job_status_not_found(self, mock_get: MagicMock) -> None:
        """Status returns None when job does not exist."""
        mock_get.return_value = None

        producer = JobProducer(db=self.db)
        status = producer.get_job_status(uuid.uuid4())
        self.assertIsNone(status)


class TestJobProducerApproval(unittest.TestCase):
    """Test the approval flow through the producer."""

    def setUp(self) -> None:
        self.db = MagicMock()

    @patch("supervisor.queue.producer.update_job_status")
    @patch("supervisor.queue.producer.complete_job")
    @patch("supervisor.queue.producer.get_execution_job")
    def test_submit_approval_approved(
        self, mock_get: MagicMock, mock_complete: MagicMock, mock_update: MagicMock
    ) -> None:
        """Submit approval decision (approved)."""
        mock_get.return_value = _make_job_db(status="awaiting_approval")
        mock_complete.return_value = True
        mock_update.return_value = True

        producer = JobProducer(db=self.db)
        decision = ApprovalDecision(approved=True, reason="Looks safe")
        result = producer.submit_approval(uuid.uuid4(), decision)
        self.assertTrue(result)

    @patch("supervisor.queue.producer.get_execution_job")
    def test_submit_approval_not_awaiting(self, mock_get: MagicMock) -> None:
        """Submit approval fails if job is not awaiting approval."""
        mock_get.return_value = _make_job_db(status="running")

        producer = JobProducer(db=self.db)
        decision = ApprovalDecision(approved=True)
        result = producer.submit_approval(uuid.uuid4(), decision)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Consumer tests
# ---------------------------------------------------------------------------


class TestJobConsumer(unittest.TestCase):
    """Test job consumer operations."""

    def setUp(self) -> None:
        self.db = MagicMock()

    @patch("supervisor.queue.consumer.get_queued_jobs")
    def test_poll_jobs(self, mock_get_queued: MagicMock) -> None:
        """Consumer polls queued jobs."""
        job = _make_job_db()
        job.id = uuid.uuid4()
        mock_get_queued.return_value = [job]

        consumer = JobConsumer(db=self.db)
        jobs = consumer.poll_jobs(limit=5)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["prompt"], "Fix bug")

    @patch("supervisor.queue.consumer.claim_job")
    def test_claim_job(self, mock_claim: MagicMock) -> None:
        """Consumer claims a queued job."""
        mock_claim.return_value = True

        consumer = JobConsumer(db=self.db)
        result = consumer.claim(uuid.uuid4())
        self.assertTrue(result)

    @patch("supervisor.queue.consumer.complete_job")
    def test_complete_job(self, mock_complete: MagicMock) -> None:
        """Consumer completes a job with result."""
        mock_complete.return_value = True

        consumer = JobConsumer(db=self.db)
        result = consumer.complete(uuid.uuid4(), {"output": "Done", "status": "completed"})
        self.assertTrue(result)

    @patch("supervisor.queue.consumer.fail_job")
    def test_fail_job(self, mock_fail: MagicMock) -> None:
        """Consumer fails a job."""
        mock_fail.return_value = True

        consumer = JobConsumer(db=self.db)
        result = consumer.fail(uuid.uuid4(), "Process crashed")
        self.assertTrue(result)

    @patch("supervisor.queue.consumer.fail_job")
    def test_fail_job_oom(self, mock_fail: MagicMock) -> None:
        """Consumer fails a job with OOM reason."""
        mock_fail.return_value = True

        consumer = JobConsumer(db=self.db)
        result = consumer.fail(uuid.uuid4(), "Container OOM-killed", reason="oom")
        self.assertTrue(result)
        mock_fail.assert_called_once()
        call_args = mock_fail.call_args
        self.assertEqual(call_args[0][3], "oom")

    @patch("supervisor.queue.consumer.update_job_status")
    @patch("supervisor.queue.consumer.get_execution_job")
    def test_request_approval(self, mock_get: MagicMock, mock_update: MagicMock) -> None:
        """Consumer requests approval for a tool call."""
        job = _make_job_db(status="running")
        mock_get.return_value = job
        mock_update.return_value = True

        consumer = JobConsumer(db=self.db)
        req = ApprovalRequest(job_id=str(job.id), tool_name="rm -rf", tool_args={"path": "/data"})
        result = consumer.request_approval(job.id, req)
        self.assertTrue(result)

    @patch("supervisor.queue.consumer.get_execution_job")
    def test_poll_approval_returns_decision(self, mock_get: MagicMock) -> None:
        """Consumer polls and finds an approval decision."""
        job = _make_job_db(
            status="awaiting_approval",
            result={"_approval_decision": {"approved": True, "reason": "OK"}},
        )
        mock_get.return_value = job

        consumer = JobConsumer(db=self.db)
        decision = consumer.poll_approval(job.id)
        self.assertIsNotNone(decision)
        self.assertTrue(decision.approved)  # type: ignore[union-attr]

    @patch("supervisor.queue.consumer.get_execution_job")
    def test_poll_approval_returns_none_when_no_decision(self, mock_get: MagicMock) -> None:
        """Consumer polls but no decision yet."""
        job = _make_job_db(status="awaiting_approval", result={})
        mock_get.return_value = job

        consumer = JobConsumer(db=self.db)
        decision = consumer.poll_approval(job.id)
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
