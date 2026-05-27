import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from api.observability.providers.base import LoggingProvider, TracingProvider

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Tracer

    from api.observability.config import ObservabilitySettings

logger = logging.getLogger(__name__)


class OTLPTracingProvider(TracingProvider):
    """OpenTelemetry Protocol (OTLP) tracing provider.

    Exports traces to any OTLP-compatible backend such as:
    - OpenTelemetry Collector
    - Jaeger (via OTLP)
    - Grafana Tempo
    - Datadog
    - Honeycomb
    - And many others

    Configure with OTEL_OTLP_ENDPOINT environment variable.
    """

    def __init__(self) -> None:
        self._config: Optional["ObservabilitySettings"] = None
        self._tracer: Optional["Tracer"] = None
        self._provider: Optional["TracerProvider"] = None
        self._initialized = False

    def initialize(self, config: "ObservabilitySettings") -> None:
        """Initialize OpenTelemetry tracing with OTLP exporter.

        Args:
            config: ObservabilitySettings with OTLP endpoint configuration.
        """
        self._config = config

        if not config.otlp_endpoint:
            logger.warning("OTLP endpoint not configured, using default localhost:4317")

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

            # Create resource with service information
            resource = Resource.create(
                {
                    SERVICE_NAME: config.service_name,
                    SERVICE_VERSION: config.service_version,
                    "deployment.environment": config.environment,
                }
            )

            # Create sampler based on sample rate
            sampler = TraceIdRatioBased(config.tracing_sample_rate)

            # Create tracer provider
            self._provider = TracerProvider(resource=resource, sampler=sampler)

            # Create OTLP exporter
            endpoint = config.otlp_endpoint or "localhost:4317"
            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                insecure=config.otlp_insecure,
            )

            # Add batch processor
            self._provider.add_span_processor(BatchSpanProcessor(exporter))

            # Set as global tracer provider
            trace.set_tracer_provider(self._provider)

            # Get tracer
            self._tracer = trace.get_tracer(config.service_name, config.service_version)

            self._initialized = True
            logger.info(
                f"OTLP tracing provider initialized (endpoint={endpoint}, "
                f"service={config.service_name}, sample_rate={config.tracing_sample_rate})"
            )

        except ImportError as e:
            logger.error(f"OpenTelemetry packages not installed: {e}")
            raise ImportError(
                "OpenTelemetry packages required. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
        except Exception as e:
            logger.error(f"Failed to initialize OTLP tracing: {e}")
            raise

    def shutdown(self) -> None:
        """Shutdown tracer provider and flush pending spans."""
        if self._provider:
            try:
                self._provider.shutdown()
                logger.debug("OTLP tracing provider shutdown")
            except Exception as e:
                logger.error(f"Error shutting down OTLP tracing: {e}")

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
        """Create an OpenTelemetry span.

        Args:
            name: Name of the span.
            attributes: Optional attributes to attach to the span.

        Yields:
            The OpenTelemetry Span object or None if not initialized.
        """
        if not self._initialized or not self._tracer:
            yield None
            return

        with self._tracer.start_as_current_span(name, attributes=attributes) as span:
            yield span

    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the current span.

        Args:
            exception: The exception to record.
        """
        if not self._initialized:
            return

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
        except Exception as e:
            logger.debug(f"Error recording exception in OTLP: {e}")

    def get_current_trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        if not self._initialized:
            return None

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().trace_id, "032x")
        except Exception:
            pass
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get the current span ID."""
        if not self._initialized:
            return None

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().span_id, "016x")
        except Exception:
            pass
        return None


class OTLPLoggingProvider(LoggingProvider):
    """OpenTelemetry Protocol (OTLP) logging provider.

    Exports logs to any OTLP-compatible backend. Logs are correlated
    with traces using trace context injection.
    """

    def __init__(self) -> None:
        self._config: Optional["ObservabilitySettings"] = None
        self._handler: Optional[logging.Handler] = None
        self._initialized = False

    def initialize(self, config: "ObservabilitySettings") -> None:
        """Initialize OpenTelemetry logging with OTLP exporter.

        Args:
            config: ObservabilitySettings with OTLP endpoint configuration.
        """
        self._config = config

    def shutdown(self) -> None:
        """Shutdown logging provider."""
        if self._handler:
            try:
                self._handler.flush()
            except Exception as e:
                logger.debug(f"Error flushing OTLP logging handler: {e}")

    def get_handler(self) -> logging.Handler:
        """Return an OTLP logging handler.

        Returns:
            A logging handler that exports to OTLP.
        """
        if self._handler is not None:
            return self._handler

        if not self._config:
            raise ValueError("OTLP logging provider not initialized")

        try:
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
                OTLPLogExporter,
            )
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource

            # Create resource
            resource = Resource.create(
                {
                    SERVICE_NAME: self._config.service_name,
                    SERVICE_VERSION: self._config.service_version,
                    "deployment.environment": self._config.environment,
                }
            )

            # Create logger provider
            logger_provider = LoggerProvider(resource=resource)

            # Create OTLP exporter
            endpoint = self._config.otlp_endpoint or "localhost:4317"
            exporter = OTLPLogExporter(
                endpoint=endpoint,
                insecure=self._config.otlp_insecure,
            )

            # Add batch processor
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

            # Set as global logger provider
            set_logger_provider(logger_provider)

            # Create logging handler
            self._handler = LoggingHandler(
                level=getattr(logging, self._config.log_level.upper(), logging.INFO),
                logger_provider=logger_provider,
            )

            self._initialized = True
            logger.info(f"OTLP logging provider initialized (endpoint={endpoint})")

            return self._handler

        except ImportError as e:
            logger.error(f"OpenTelemetry logging packages not installed: {e}")
            raise ImportError(
                "OpenTelemetry logging packages required. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
        except Exception as e:
            logger.error(f"Failed to initialize OTLP logging: {e}")
            raise
