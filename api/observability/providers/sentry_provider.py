import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from api.observability.providers.base import TracingProvider

if TYPE_CHECKING:
    from api.observability.config import ObservabilitySettings

logger = logging.getLogger(__name__)


class SentryTracingProvider(TracingProvider):
    """Sentry-based tracing provider for error tracking and performance monitoring.

    This provider bridges to Sentry's SDK, maintaining backward compatibility
    with existing Sentry integrations. It uses the SENTRY_DSN environment
    variable or configuration settings.
    """

    def __init__(self) -> None:
        self._config: Optional["ObservabilitySettings"] = None
        self._initialized = False

    def initialize(self, config: "ObservabilitySettings") -> None:
        """Initialize Sentry SDK with configuration.

        Args:
            config: ObservabilitySettings with Sentry-specific settings.
        """
        self._config = config

        if not config.sentry_dsn:
            logger.warning("Sentry DSN not configured, Sentry provider will not send data")
            return

        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=config.sentry_dsn,
                environment=config.environment,
                # Add data like request headers and IP for users
                send_default_pii=True,
                # Tracing sample rate
                traces_sample_rate=config.sentry_traces_sample_rate,
                # Profiling sample rate
                profile_session_sample_rate=config.sentry_profiles_sample_rate,
                # Auto-profiler on active transactions
                profile_lifecycle="trace",
            )
            self._initialized = True
            logger.info(
                f"Sentry tracing provider initialized (environment={config.environment}, "
                f"traces_sample_rate={config.sentry_traces_sample_rate})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")

    def shutdown(self) -> None:
        """Flush pending events to Sentry."""
        if not self._initialized:
            return

        try:
            import sentry_sdk

            sentry_sdk.flush()
            logger.debug("Sentry events flushed")
        except Exception as e:
            logger.error(f"Error flushing Sentry events: {e}")

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
        """Create a Sentry transaction span.

        Args:
            name: Name of the span/operation.
            attributes: Optional data to attach to the span.

        Yields:
            The Sentry span object or None if not initialized.
        """
        if not self._initialized:
            yield None
            return

        try:
            import sentry_sdk

            with sentry_sdk.start_span(op=name, description=name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_data(key, value)
                yield span
        except Exception as e:
            logger.debug(f"Error creating Sentry span: {e}")
            yield None

    def record_exception(self, exception: Exception) -> None:
        """Capture an exception in Sentry.

        Args:
            exception: The exception to capture.
        """
        if not self._initialized:
            return

        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exception)
        except Exception as e:
            logger.debug(f"Error capturing exception in Sentry: {e}")

    def get_current_trace_id(self) -> Optional[str]:
        """Get the current Sentry trace ID."""
        if not self._initialized:
            return None

        try:
            import sentry_sdk

            scope = sentry_sdk.get_current_scope()
            if scope and scope.span:
                return scope.span.trace_id
        except Exception:
            pass
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get the current Sentry span ID."""
        if not self._initialized:
            return None

        try:
            import sentry_sdk

            scope = sentry_sdk.get_current_scope()
            if scope and scope.span:
                return scope.span.span_id
        except Exception:
            pass
        return None
