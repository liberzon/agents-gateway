import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from supervisor.models import StreamEvent, StreamVerbosity

logger = logging.getLogger(__name__)

# In-memory event buffer for active jobs
_event_buffers: Dict[str, List[StreamEvent]] = defaultdict(list)
_event_signals: Dict[str, asyncio.Event] = {}


def _get_signal(job_id: str) -> asyncio.Event:
    if job_id not in _event_signals:
        _event_signals[job_id] = asyncio.Event()
    return _event_signals[job_id]


def emit_event(job_id: str, event_type: str, content: Any = None, worker_id: Optional[str] = None) -> None:
    """Publish a stream event for a job."""
    event = StreamEvent(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        worker_id=worker_id,
        content=content,
    )
    _event_buffers[job_id].append(event)
    signal = _get_signal(job_id)
    signal.set()


def _should_include(event: StreamEvent, verbosity: StreamVerbosity) -> bool:
    """Filter events based on verbosity level."""
    if verbosity == StreamVerbosity.full:
        return True

    if verbosity == StreamVerbosity.result:
        return event.event_type in ("message", "error", "status")

    # events (default): tool calls, status changes, messages — not thinking or raw tool results
    return event.event_type in ("tool_call", "message", "status", "approval_request", "error")


def _format_sse(event: StreamEvent) -> str:
    data = {
        "timestamp": event.timestamp.isoformat(),
        "event_type": event.event_type,
        "worker_id": event.worker_id,
        "content": event.content,
    }
    return f"data: {json.dumps(data)}\n\n"


async def create_stream(
    job_id: str,
    verbosity: StreamVerbosity = StreamVerbosity.events,
    timeout: float = 900.0,
) -> AsyncGenerator[str, None]:
    """Create an SSE stream for a job, filtered by verbosity."""
    cursor = 0
    elapsed = 0.0
    poll_interval = 0.5

    while elapsed < timeout:
        signal = _get_signal(job_id)

        # Drain buffered events from cursor
        events = _event_buffers.get(job_id, [])
        while cursor < len(events):
            event = events[cursor]
            cursor += 1
            if _should_include(event, verbosity):
                yield _format_sse(event)

        # Check for terminal events
        if events and events[-1].event_type in ("done", "error"):
            break

        # Wait for new events
        signal.clear()
        try:
            await asyncio.wait_for(signal.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            elapsed += poll_interval

    # Final drain
    events = _event_buffers.get(job_id, [])
    while cursor < len(events):
        event = events[cursor]
        cursor += 1
        if _should_include(event, verbosity):
            yield _format_sse(event)


def cleanup_stream(job_id: str) -> None:
    """Clean up event buffer and signal for a completed job."""
    _event_buffers.pop(job_id, None)
    _event_signals.pop(job_id, None)
