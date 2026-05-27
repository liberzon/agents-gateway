import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from supervisor.models import JobSpec, WorkerConfig

logger = logging.getLogger(__name__)

# Runtime configuration
RUNTIME_TYPE = os.environ.get("CONTAINER_RUNTIME", "docker")  # docker or kubernetes
WORKER_IMAGE = os.environ.get("WORKER_IMAGE", "claude-code-worker:latest")
K8S_NAMESPACE = os.environ.get("K8S_NAMESPACE", "supervisor-workers")
JOB_CONSUMER_ENABLED = os.environ.get("JOB_CONSUMER_ENABLED", "false").lower() == "true"
JOB_CONSUMER_POLL_INTERVAL = float(os.environ.get("JOB_CONSUMER_POLL_INTERVAL", "5.0"))

_consumer_task: Optional[asyncio.Task[None]] = None


async def _run_job_consumer_loop(poll_interval: float = 5.0) -> None:
    """Background loop that polls the job queue and executes claimed jobs."""
    from supervisor.queue.consumer import JobConsumer

    logger.info("JobConsumer background loop started")
    while True:
        try:
            from db.session import get_db as _get_db

            db = next(_get_db())
            try:
                consumer = JobConsumer(db=db)
                jobs = consumer.poll_jobs(limit=5)
                for job_data in jobs:
                    from uuid import UUID

                    job_id = UUID(job_data["id"])
                    if consumer.claim(job_id):
                        logger.info(f"Claimed job {job_id}, executing...")
                        executor = _get_executor()
                        worker_config = WorkerConfig(**job_data["worker_config"])
                        try:
                            result = await executor.execute(
                                prompt=job_data["prompt"],
                                worker_config=worker_config,
                                memory_limit_mb=job_data.get("memory_limit_mb"),
                            )
                            consumer.complete(job_id, result.model_dump())
                            logger.info(f"Job {job_id} completed: {result.status}")
                        except Exception as exec_err:
                            consumer.fail(job_id, str(exec_err))
                            logger.error(f"Job {job_id} failed: {exec_err}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"JobConsumer loop error: {e}")
        await asyncio.sleep(poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start/stop the JobConsumer background task."""
    global _consumer_task
    if JOB_CONSUMER_ENABLED:
        _consumer_task = asyncio.create_task(_run_job_consumer_loop(JOB_CONSUMER_POLL_INTERVAL))
        logger.info("JobConsumer background task scheduled")
    yield
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        logger.info("JobConsumer background task stopped")


app = FastAPI(title="Remote Agent Service", version="1.0", lifespan=lifespan)


def _get_runtime():  # type: ignore[no-untyped-def]
    if RUNTIME_TYPE == "kubernetes":
        from remote_agent.runtime.kubernetes import KubernetesRuntime

        return KubernetesRuntime(namespace=K8S_NAMESPACE)
    else:
        from remote_agent.runtime.docker import DockerRuntime

        return DockerRuntime()


def _get_executor():  # type: ignore[no-untyped-def]
    from remote_agent.executor import ContainerExecutor

    return ContainerExecutor(runtime=_get_runtime(), worker_image=WORKER_IMAGE)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ExecuteRequest(BaseModel):
    prompt: str
    worker_config: Dict[str, Any]
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
    model: str = "claude-sonnet-4-6"
    max_turns: int = 10
    timeout_minutes: int = 15
    memory_limit_mb: Optional[int] = None
    cpu_limit: Optional[float] = None
    network_enabled: bool = False
    job_spec: Optional[Dict[str, Any]] = None


class CancelRequest(BaseModel):
    container_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/execute", response_model=Dict[str, Any])
async def execute(body: ExecuteRequest) -> Dict[str, Any]:
    """Execute a worker task in an isolated container."""
    executor = _get_executor()
    worker_config = WorkerConfig(**body.worker_config)
    job_spec = JobSpec(**body.job_spec) if body.job_spec else None

    result = await executor.execute(
        prompt=body.prompt,
        worker_config=worker_config,
        job_spec=job_spec,
        repo_url=body.repo_url,
        model=body.model,
        max_turns=body.max_turns,
        timeout_minutes=body.timeout_minutes,
        memory_limit_mb=body.memory_limit_mb,
        cpu_limit=body.cpu_limit,
        network_enabled=body.network_enabled,
    )
    return result.model_dump()


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check — verify runtime is available."""
    runtime = _get_runtime()
    healthy = await runtime.health_check()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "runtime": RUNTIME_TYPE,
        "worker_image": WORKER_IMAGE,
    }


@app.get("/jobs/active")
async def active_jobs() -> Dict[str, Any]:
    """List currently running containers/jobs."""
    # Placeholder — would query runtime for active containers with supervisor=true label
    return {"active_jobs": [], "runtime": RUNTIME_TYPE}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> Dict[str, str]:
    """Cancel a running job by destroying its container."""
    runtime = _get_runtime()
    try:
        await runtime.destroy_container(job_id)
        return {"status": "cancelled", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
