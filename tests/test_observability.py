import logging
import unittest
from unittest.mock import MagicMock, patch

from api.observability.config import LoggingBackend, ObservabilitySettings, TracingBackend
from api.observability.providers.base import LoggingProvider, TracingProvider
from api.observability.providers.console import ConsoleLoggingProvider, ConsoleTracingProvider


class TestObservabilitySettings(unittest.TestCase):
    """Test ObservabilitySettings configuration."""

    def test_default_settings(self):
        """Test default configuration values."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_SERVICE_NAME": "test-service",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.service_name, "test-service")
            self.assertEqual(settings.tracing_backend, TracingBackend.CONSOLE)
            self.assertEqual(settings.logging_backends, [LoggingBackend.CONSOLE])
            self.assertEqual(settings.log_level, "INFO")
            self.assertEqual(settings.tracing_sample_rate, 1.0)

    def test_sentry_backend_configuration(self):
        """Test Sentry backend configuration."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "sentry",
                "SENTRY_DSN": "https://test@sentry.io/123",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.SENTRY)
            self.assertEqual(settings.sentry_dsn, "https://test@sentry.io/123")

    def test_multiple_logging_backends(self):
        """Test parsing comma-separated logging backends."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_LOGGING_BACKEND": "console,logtail",
                "BETTERSTACK_SOURCE_TOKEN": "test-token",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertIn(LoggingBackend.CONSOLE, settings.logging_backends)
            self.assertIn(LoggingBackend.LOGTAIL, settings.logging_backends)

    def test_otlp_configuration(self):
        """Test OTLP backend configuration."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "otlp",
                "OTEL_OTLP_ENDPOINT": "http://collector:4317",
                "OTEL_OTLP_INSECURE": "true",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.OTLP)
            self.assertEqual(settings.otlp_endpoint, "http://collector:4317")
            self.assertTrue(settings.otlp_insecure)

    def test_sample_rate_validation(self):
        """Test that sample rate is clamped to valid range."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_SAMPLE_RATE": "1.5",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 1.0)

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_SAMPLE_RATE": "-0.5",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 0.0)


class TestConsoleTracingProvider(unittest.TestCase):
    """Test ConsoleTracingProvider."""

    def setUp(self):
        self.provider = ConsoleTracingProvider()
        self.config = MagicMock()
        self.config.service_name = "test-service"
        self.config.log_level = "DEBUG"

    def test_initialize(self):
        """Test provider initialization."""
        self.provider.initialize(self.config)
        # Should not raise

    def test_span_context_manager(self):
        """Test span context manager."""
        self.provider.initialize(self.config)
        with self.provider.span("test-span", {"key": "value"}) as span:
            self.assertIsNone(span)  # Console provider returns None

    def test_span_without_initialization(self):
        """Test span returns None when not initialized."""
        with self.provider.span("test-span") as span:
            self.assertIsNone(span)

    def test_record_exception(self):
        """Test exception recording."""
        self.provider.initialize(self.config)
        # Should not raise
        self.provider.record_exception(ValueError("test error"))

    def test_get_current_trace_id(self):
        """Test trace ID retrieval."""
        self.provider.initialize(self.config)
        trace_id = self.provider.get_current_trace_id()
        self.assertIsNone(trace_id)  # Console provider always returns None

    def test_get_current_span_id(self):
        """Test span ID retrieval."""
        self.provider.initialize(self.config)
        span_id = self.provider.get_current_span_id()
        self.assertIsNone(span_id)  # Console provider always returns None

    def test_shutdown(self):
        """Test provider shutdown."""
        self.provider.initialize(self.config)
        self.provider.shutdown()
        # Should not raise


class TestConsoleLoggingProvider(unittest.TestCase):
    """Test ConsoleLoggingProvider."""

    def setUp(self):
        self.provider = ConsoleLoggingProvider()
        self.config = MagicMock()
        self.config.log_level = "DEBUG"
        self.config.service_name = "test-service"

    def test_initialize(self):
        """Test provider initialization."""
        self.provider.initialize(self.config)
        # Should not raise

    def test_get_handler(self):
        """Test getting logging handler."""
        self.provider.initialize(self.config)
        handler = self.provider.get_handler()
        self.assertIsInstance(handler, logging.Handler)

    def test_get_handler_caches_result(self):
        """Test that handler is cached."""
        self.provider.initialize(self.config)
        handler1 = self.provider.get_handler()
        handler2 = self.provider.get_handler()
        self.assertIs(handler1, handler2)

    def test_shutdown(self):
        """Test provider shutdown."""
        self.provider.initialize(self.config)
        self.provider.get_handler()
        self.provider.shutdown()
        # Should not raise


class TestObservabilityManager(unittest.TestCase):
    """Test ObservabilityManager."""

    def setUp(self):
        # Reset the singleton for each test
        from api.observability import observability

        observability._tracing_provider = None
        observability._logging_providers = []
        observability._initialized = False

    def test_initialize_with_console_backend(self):
        """Test initialization with console backend."""
        from api.observability import observability

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            observability.initialize(config)
            self.assertTrue(observability.is_initialized)

    def test_initialize_only_once(self):
        """Test that initialization only happens once."""
        from api.observability import observability

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            observability.initialize(config)
            first_provider = observability._tracing_provider

            observability.initialize(config)
            second_provider = observability._tracing_provider

            self.assertIs(first_provider, second_provider)

    def test_span_context_manager(self):
        """Test span context manager through manager."""
        from api.observability import observability

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            observability.initialize(config)

            with observability.span("test-span") as span:
                self.assertIsNone(span)

    def test_record_exception(self):
        """Test exception recording through manager."""
        from api.observability import observability

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            observability.initialize(config)
            # Should not raise
            observability.record_exception(ValueError("test"))

    def test_shutdown(self):
        """Test shutdown."""
        from api.observability import observability

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            observability.initialize(config)
            observability.shutdown()
            # After shutdown, is_initialized should still be True
            # (we don't reset the flag to allow for graceful shutdown)


class TestTracingProviderInterface(unittest.TestCase):
    """Test that TracingProvider interface is properly defined."""

    def test_interface_methods_exist(self):
        """Test that all interface methods are defined."""
        self.assertTrue(hasattr(TracingProvider, "initialize"))
        self.assertTrue(hasattr(TracingProvider, "shutdown"))
        self.assertTrue(hasattr(TracingProvider, "span"))
        self.assertTrue(hasattr(TracingProvider, "record_exception"))
        self.assertTrue(hasattr(TracingProvider, "get_current_trace_id"))
        self.assertTrue(hasattr(TracingProvider, "get_current_span_id"))


class TestLoggingProviderInterface(unittest.TestCase):
    """Test that LoggingProvider interface is properly defined."""

    def test_interface_methods_exist(self):
        """Test that all interface methods are defined."""
        self.assertTrue(hasattr(LoggingProvider, "initialize"))
        self.assertTrue(hasattr(LoggingProvider, "shutdown"))
        self.assertTrue(hasattr(LoggingProvider, "get_handler"))


class TestSentryProviderInitialization(unittest.TestCase):
    """Test SentryTracingProvider initialization."""

    @patch("sentry_sdk.init")
    def test_sentry_provider_initialize(self, mock_sentry_init):
        """Test Sentry provider calls sentry_sdk.init."""
        from api.observability.providers.sentry_provider import SentryTracingProvider

        provider = SentryTracingProvider()
        config = MagicMock()
        config.sentry_dsn = "https://test@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 0.5
        config.sentry_profiles_sample_rate = 0.1

        provider.initialize(config)

        mock_sentry_init.assert_called_once()
        call_kwargs = mock_sentry_init.call_args[1]
        self.assertEqual(call_kwargs["dsn"], "https://test@sentry.io/123")
        self.assertEqual(call_kwargs["environment"], "test")
        self.assertEqual(call_kwargs["traces_sample_rate"], 0.5)


class TestLogtailProviderInitialization(unittest.TestCase):
    """Test LogtailLoggingProvider initialization."""

    def test_logtail_provider_requires_token(self):
        """Test that Logtail provider requires token."""
        from api.observability.providers.logtail_provider import LogtailLoggingProvider

        provider = LogtailLoggingProvider()
        config = MagicMock()
        config.betterstack_source_token = None

        provider.initialize(config)

        with self.assertRaises(ValueError):
            provider.get_handler()


if __name__ == "__main__":
    unittest.main()
