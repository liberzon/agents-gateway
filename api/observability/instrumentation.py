import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

    from api.observability.config import ObservabilitySettings

logger = logging.getLogger(__name__)


def setup_auto_instrumentation(app: "FastAPI", config: "ObservabilitySettings") -> None:
    """Configure OpenTelemetry auto-instrumentation for common libraries.

    This sets up automatic tracing for:
    - FastAPI: HTTP requests and responses
    - HTTPX: Outgoing HTTP client requests
    - SQLAlchemy: Database queries
    - Requests: Outgoing HTTP requests (if used)

    Auto-instrumentation is only enabled for the OTLP backend,
    which uses the OpenTelemetry SDK internally.

    Args:
        app: The FastAPI application instance.
        config: ObservabilitySettings with tracing configuration.
    """
    from api.observability.config import TracingBackend

    # Only enable auto-instrumentation for OTEL-based backends
    if config.tracing_backend != TracingBackend.OTLP:
        logger.debug(f"Skipping auto-instrumentation for backend: {config.tracing_backend.value}")
        return

    instrumented = []

    # FastAPI instrumentation
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        instrumented.append("FastAPI")
    except ImportError:
        logger.debug("FastAPI instrumentation not available")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")

    # HTTPX instrumentation (async HTTP client used by this app)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        instrumented.append("HTTPX")
    except ImportError:
        logger.debug("HTTPX instrumentation not available")
    except Exception as e:
        logger.warning(f"Failed to instrument HTTPX: {e}")

    # SQLAlchemy instrumentation
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # Import engine lazily to avoid circular imports
        from db.session import db_engine

        SQLAlchemyInstrumentor().instrument(engine=db_engine)
        instrumented.append("SQLAlchemy")
    except ImportError:
        logger.debug("SQLAlchemy instrumentation not available")
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")

    # Requests instrumentation (if using requests library)
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        instrumented.append("Requests")
    except ImportError:
        logger.debug("Requests instrumentation not available")
    except Exception as e:
        logger.warning(f"Failed to instrument Requests: {e}")

    if instrumented:
        logger.info(f"Auto-instrumentation enabled for: {', '.join(instrumented)}")
    else:
        logger.warning("No auto-instrumentation enabled")


def uninstrument_all() -> None:
    """Remove all auto-instrumentation.

    Useful for testing or when dynamically changing backends.
    """
    uninstrumented = []

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().uninstrument()
        uninstrumented.append("FastAPI")
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().uninstrument()
        uninstrumented.append("HTTPX")
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().uninstrument()
        uninstrumented.append("SQLAlchemy")
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().uninstrument()
        uninstrumented.append("Requests")
    except Exception:
        pass

    if uninstrumented:
        logger.info(f"Auto-instrumentation removed for: {', '.join(uninstrumented)}")
