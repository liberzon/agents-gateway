import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

if TYPE_CHECKING:
    from api.observability.config import ObservabilitySettings


class TracingProvider(ABC):
    """Abstract base class for tracing providers.

    Tracing providers handle distributed tracing with spans that track
    request flows through the application. Implementations can export
    traces to various backends like OTLP collectors, Jaeger, or Sentry.
    """

    @abstractmethod
    def initialize(self, config: "ObservabilitySettings") -> None:
        """Initialize the tracing provider with configuration.

        Args:
            config: ObservabilitySettings instance with provider-specific settings.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup and flush any pending traces.

        Called during application shutdown to ensure all traces are exported.
        """
        pass

    @abstractmethod
    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
        """Create a trace span context manager.

        Args:
            name: Name of the span (e.g., "http_request", "database_query").
            attributes: Optional key-value pairs to attach to the span.

        Yields:
            The span object (implementation-specific) or None.
        """
        pass

    @abstractmethod
    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the current span.

        Args:
            exception: The exception to record.
        """
        pass

    def get_current_trace_id(self) -> Optional[str]:
        """Get the current trace ID if available.

        Returns:
            The trace ID as a string, or None if not available.
        """
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get the current span ID if available.

        Returns:
            The span ID as a string, or None if not available.
        """
        return None


class LoggingProvider(ABC):
    """Abstract base class for logging providers.

    Logging providers create Python logging handlers that can send logs
    to various backends like stdout, OTLP collectors, or Logtail/Better Stack.
    """

    @abstractmethod
    def initialize(self, config: "ObservabilitySettings") -> None:
        """Initialize the logging provider with configuration.

        Args:
            config: ObservabilitySettings instance with provider-specific settings.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup and flush any pending logs.

        Called during application shutdown to ensure all logs are sent.
        """
        pass

    @abstractmethod
    def get_handler(self) -> logging.Handler:
        """Return a logging handler for this provider.

        Returns:
            A configured logging.Handler instance.
        """
        pass
