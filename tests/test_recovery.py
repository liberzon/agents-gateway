"""Tests for OOM recovery and circuit breaker."""

import unittest

from supervisor.models import RetryPolicy
from supervisor.recovery import RetryAction, is_oom_exit


class TestIsOomExit(unittest.TestCase):
    def test_docker_oom(self) -> None:
        assert is_oom_exit(exit_code=137) is True

    def test_k8s_oom(self) -> None:
        assert is_oom_exit(k8s_reason="OOMKilled") is True

    def test_normal_exit(self) -> None:
        assert is_oom_exit(exit_code=0) is False

    def test_other_failure(self) -> None:
        assert is_oom_exit(exit_code=1) is False

    def test_no_info(self) -> None:
        assert is_oom_exit() is False


class TestRetryPolicy(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_retries == 2
        assert policy.memory_multiplier == 2.0
        assert policy.enable_supervisor_replan is True
        assert policy.circuit_breaker_threshold == 3

    def test_custom(self) -> None:
        policy = RetryPolicy(max_retries=5, memory_multiplier=1.5, circuit_breaker_threshold=10)
        assert policy.max_retries == 5
        assert policy.memory_multiplier == 1.5


class TestRetryAction(unittest.TestCase):
    def test_enum_values(self) -> None:
        assert RetryAction.retry == "retry"
        assert RetryAction.replan == "replan"
        assert RetryAction.circuit_open == "circuit_open"


if __name__ == "__main__":
    unittest.main()
