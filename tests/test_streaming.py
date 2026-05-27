"""Tests for streaming with configurable verbosity."""

import unittest

from supervisor.models import StreamVerbosity
from supervisor.streaming import _should_include, StreamEvent, cleanup_stream, emit_event


class TestStreamVerbosityFiltering(unittest.TestCase):
    def _make_event(self, event_type: str) -> StreamEvent:
        return StreamEvent(event_type=event_type, content="test")

    def test_full_includes_everything(self) -> None:
        for event_type in ["thinking", "tool_call", "tool_result", "message", "status", "error"]:
            event = self._make_event(event_type)
            assert _should_include(event, StreamVerbosity.full) is True

    def test_events_includes_tool_calls_and_messages(self) -> None:
        assert _should_include(self._make_event("tool_call"), StreamVerbosity.events) is True
        assert _should_include(self._make_event("message"), StreamVerbosity.events) is True
        assert _should_include(self._make_event("status"), StreamVerbosity.events) is True
        assert _should_include(self._make_event("error"), StreamVerbosity.events) is True
        assert _should_include(self._make_event("approval_request"), StreamVerbosity.events) is True

    def test_events_excludes_thinking_and_tool_results(self) -> None:
        assert _should_include(self._make_event("thinking"), StreamVerbosity.events) is False
        assert _should_include(self._make_event("tool_result"), StreamVerbosity.events) is False

    def test_result_only_includes_final(self) -> None:
        assert _should_include(self._make_event("message"), StreamVerbosity.result) is True
        assert _should_include(self._make_event("error"), StreamVerbosity.result) is True
        assert _should_include(self._make_event("status"), StreamVerbosity.result) is True

    def test_result_excludes_intermediate(self) -> None:
        assert _should_include(self._make_event("tool_call"), StreamVerbosity.result) is False
        assert _should_include(self._make_event("thinking"), StreamVerbosity.result) is False
        assert _should_include(self._make_event("tool_result"), StreamVerbosity.result) is False


class TestEmitEvent(unittest.TestCase):
    def test_emit_and_cleanup(self) -> None:
        job_id = "test-job-123"
        emit_event(job_id, "message", "hello")
        emit_event(job_id, "status", "running")

        from supervisor.streaming import _event_buffers

        assert job_id in _event_buffers
        assert len(_event_buffers[job_id]) == 2

        cleanup_stream(job_id)
        assert job_id not in _event_buffers


if __name__ == "__main__":
    unittest.main()
