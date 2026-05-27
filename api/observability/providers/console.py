import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from api.observability.providers.base import LoggingProvider, TracingProvider

if TYPE_CHECKING:
    from api.observability.config import ObservabilitySettings


class ConsoleTracingProvider(TracingProvider):
    """Console-based tracing for development and debugging.

    Outputs span information to the console using Python's logging module.
    Useful for local development when external tracing backends are not available.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("observability.tracing")
        self._config: Optional["ObservabilitySettings"] = None

    def initialize(self, config: "ObservabilitySettings") -> None:
        self._config = config
        self._logger.debug("Console tracing provider initialized")

    def shutdown(self) -> None:
        self._logger.debug("Console tracing provider shutdown")

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[None, None, None]:
        start_time = datetime.now(timezone.utc)
        self._logger.debug(f"[SPAN START] {name} attrs={attributes}")
        try:
            yield None
        except Exception as e:
            self._logger.error(f"[SPAN ERROR] {name}: {e}")
            raise
        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self._logger.debug(f"[SPAN END] {name} duration={duration:.2f}ms")

    def record_exception(self, exception: Exception) -> None:
        self._logger.exception(f"[EXCEPTION] {type(exception).__name__}: {exception}")


class ConsoleLoggingProvider(LoggingProvider):
    """Console logging with human-readable output.

    Outputs logs to stdout with timestamps, logger name, and log level.
    This is the default logging provider for development.
    """

    def __init__(self) -> None:
        self._config: Optional["ObservabilitySettings"] = None
        self._handler: Optional[logging.Handler] = None

    def initialize(self, config: "ObservabilitySettings") -> None:
        self._config = config

    def shutdown(self) -> None:
        if self._handler:
            self._handler.flush()

    def get_handler(self) -> logging.Handler:
        if self._handler is None:
            self._handler = logging.StreamHandler(sys.stdout)
            self._handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        return self._handler
