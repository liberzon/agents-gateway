import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from api.observability.config import (
    LoggingBackend,
    ObservabilitySettings,
    TracingBackend,
)
from api.observability.providers.base import LoggingProvider, TracingProvider
from api.observability.providers.console import (
    ConsoleLoggingProvider,
    ConsoleTracingProvider,
)


class ObservabilityManager:
    """Central manager for all observability concerns.

    This class orchestrates tracing and logging providers based on configuration.
    It supports multiple logging backends simultaneously and a single tracing backend.

    Usage:
        from api.observability import observability

        # Initialize with default or custom settings
        observability.initialize()

        # Use tracing
        with observability.span("my_operation"):
            do_something()

        # Shutdown on app exit
        observability.shutdown()
    """

    _instance: Optional["ObservabilityManager"] = None

    def __init__(self) -> None:
        self._config: Optional[ObservabilitySettings] = None
        self._tracing_provider: Optional[TracingProvider] = None
        self._logging_providers: List[LoggingProvider] = []
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "ObservabilityManager":
        """Get the singleton instance of ObservabilityManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        if cls._instance is not None:
            cls._instance.shutdown()
            cls._instance = None

    @property
    def is_initialized(self) -> bool:
        """Check if the manager has been initialized."""
        return self._initialized

    def initialize(self, config: Optional[ObservabilitySettings] = None) -> None:
        """Initialize all observability providers based on configuration.

        Args:
            config: Optional custom configuration. If not provided, uses default settings.
        """
        if self._initialized:
            return

        self._config = config or ObservabilitySettings()

        # Skip full initialization in test mode
        is_testing = os.getenv("TESTING", "false").lower() == "true"
        if is_testing:
            self._setup_console_only()
            self._initialized = True
            logging.info("Observability initialized (test mode - console only)")
            return

        self._setup_tracing()
        self._setup_logging()
        self._initialized = True
        logging.info(
            f"Observability initialized: tracing={self._config.tracing_backend.value}, "
            f"logging={[b.value for b in self._config.logging_backends]}"
        )

    def _setup_console_only(self) -> None:
        """Minimal setup for testing environment."""
        assert self._config is not None

        self._tracing_provider = ConsoleTracingProvider()
        self._tracing_provider.initialize(self._config)

        provider = ConsoleLoggingProvider()
        provider.initialize(self._config)
        self._logging_providers.append(provider)
        self._configure_root_logger()

    def _setup_tracing(self) -> None:
        """Initialize tracing provider based on configuration."""
        assert self._config is not None

        if not self._config.tracing_enabled:
            return

        backend = self._config.tracing_backend

        if backend == TracingBackend.NONE:
            return
        elif backend == TracingBackend.CONSOLE:
            self._tracing_provider = ConsoleTracingProvider()
        elif backend == TracingBackend.OTLP:
            try:
                from api.observability.providers.otlp import OTLPTracingProvider

                self._tracing_provider = OTLPTracingProvider()
            except ImportError:
                logging.warning("OTLP provider not available, falling back to console")
                self._tracing_provider = ConsoleTracingProvider()
        elif backend == TracingBackend.SENTRY:
            try:
                from api.observability.providers.sentry_provider import (
                    SentryTracingProvider,
                )

                self._tracing_provider = SentryTracingProvider()
            except ImportError:
                logging.warning("Sentry provider not available, falling back to console")
                self._tracing_provider = ConsoleTracingProvider()

        if self._tracing_provider:
            self._tracing_provider.initialize(self._config)

    def _setup_logging(self) -> None:
        """Initialize logging providers based on configuration."""
        assert self._config is not None

        for backend in self._config.logging_backends:
            provider: Optional[LoggingProvider] = None

            if backend == LoggingBackend.CONSOLE:
                provider = ConsoleLoggingProvider()
            elif backend == LoggingBackend.OTLP:
                try:
                    from api.observability.providers.otlp import OTLPLoggingProvider

                    provider = OTLPLoggingProvider()
                except ImportError:
                    logging.warning("OTLP logging provider not available")
            elif backend == LoggingBackend.LOGTAIL:
                try:
                    from api.observability.providers.logtail_provider import (
                        LogtailLoggingProvider,
                    )

                    provider = LogtailLoggingProvider()
                except ImportError:
                    logging.warning("Logtail logging provider not available")

            if provider:
                try:
                    provider.initialize(self._config)
                    self._logging_providers.append(provider)
                except Exception as e:
                    logging.warning(f"Failed to initialize {backend.value} logging provider: {e}")

        # Ensure at least console logging is available
        if not self._logging_providers:
            fallback = ConsoleLoggingProvider()
            fallback.initialize(self._config)
            self._logging_providers.append(fallback)

        self._configure_root_logger()

    def _configure_root_logger(self) -> None:
        """Configure Python's root logger with all providers."""
        assert self._config is not None

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self._config.log_level.upper(), logging.INFO))
        root_logger.handlers.clear()

        for provider in self._logging_providers:
            try:
                handler = provider.get_handler()
                root_logger.addHandler(handler)
            except Exception as e:
                # Fallback to console if provider fails
                logging.error(f"Failed to get handler from logging provider: {e}")

        # Suppress verbose third-party loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def shutdown(self) -> None:
        """Cleanup all providers and flush pending data."""
        if self._tracing_provider:
            try:
                self._tracing_provider.shutdown()
            except Exception as e:
                logging.error(f"Error shutting down tracing provider: {e}")

        for provider in self._logging_providers:
            try:
                provider.shutdown()
            except Exception as e:
                logging.error(f"Error shutting down logging provider: {e}")

        self._tracing_provider = None
        self._logging_providers.clear()
        self._initialized = False

    # Convenience methods for application use

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
        """Create a trace span.

        Args:
            name: Name of the span.
            attributes: Optional attributes to attach to the span.

        Yields:
            The span object or None if tracing is not available.
        """
        if self._tracing_provider:
            with self._tracing_provider.span(name, attributes) as s:
                yield s
        else:
            yield None

    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the current span.

        Args:
            exception: The exception to record.
        """
        if self._tracing_provider:
            self._tracing_provider.record_exception(exception)

    def get_current_trace_id(self) -> Optional[str]:
        """Get the current trace ID if available."""
        if self._tracing_provider:
            return self._tracing_provider.get_current_trace_id()
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get the current span ID if available."""
        if self._tracing_provider:
            return self._tracing_provider.get_current_span_id()
        return None


# Global singleton instance
observability = ObservabilityManager.get_instance()

__all__ = [
    "ObservabilityManager",
    "ObservabilitySettings",
    "TracingBackend",
    "LoggingBackend",
    "observability",
]
