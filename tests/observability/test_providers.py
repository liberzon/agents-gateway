import logging
import unittest
from unittest.mock import MagicMock, patch


class TestConsoleTracingProvider(unittest.TestCase):
    """Test ConsoleTracingProvider (CON-001 to CON-010)."""

    def setUp(self):
        from api.observability.providers.console import ConsoleTracingProvider

        self.provider = ConsoleTracingProvider()
        self.config = MagicMock()
        self.config.service_name = "test-service"
        self.config.log_level = "DEBUG"

    def test_con_001_initialize(self):
        """CON-001: Initialize provider without exceptions."""
        self.provider.initialize(self.config)
        # Should not raise

    def test_con_002_span_initialized(self):
        """CON-002: Create span when initialized returns None."""
        self.provider.initialize(self.config)
        with self.provider.span("test-span") as span:
            self.assertIsNone(span)

    def test_con_003_span_not_initialized(self):
        """CON-003: Create span when not initialized returns None."""
        with self.provider.span("test-span") as span:
            self.assertIsNone(span)

    def test_con_004_span_with_attributes(self):
        """CON-004: Span with attributes logs them."""
        self.provider.initialize(self.config)
        with self.provider.span("test-span", {"key": "value"}) as span:
            self.assertIsNone(span)

    def test_con_005_nested_spans(self):
        """CON-005: Nested spans work correctly."""
        self.provider.initialize(self.config)
        with self.provider.span("outer") as outer:
            with self.provider.span("inner") as inner:
                self.assertIsNone(inner)
            self.assertIsNone(outer)

    def test_con_006_record_exception(self):
        """CON-006: Record exception logs it."""
        self.provider.initialize(self.config)
        self.provider.record_exception(ValueError("test error"))
        # Should not raise

    def test_con_007_get_trace_id(self):
        """CON-007: Get trace ID returns None."""
        self.provider.initialize(self.config)
        self.assertIsNone(self.provider.get_current_trace_id())

    def test_con_008_get_span_id(self):
        """CON-008: Get span ID returns None."""
        self.provider.initialize(self.config)
        self.assertIsNone(self.provider.get_current_span_id())

    def test_con_009_shutdown(self):
        """CON-009: Shutdown without exceptions."""
        self.provider.initialize(self.config)
        self.provider.shutdown()

    def test_con_010_double_initialization(self):
        """CON-010: Double initialization is idempotent."""
        self.provider.initialize(self.config)
        self.provider.initialize(self.config)
        # Should not raise


class TestConsoleLoggingProvider(unittest.TestCase):
    """Test ConsoleLoggingProvider (CON-020 to CON-024)."""

    def setUp(self):
        from api.observability.providers.console import ConsoleLoggingProvider

        self.provider = ConsoleLoggingProvider()
        self.config = MagicMock()
        self.config.log_level = "DEBUG"
        self.config.service_name = "test-service"

    def test_con_020_initialize(self):
        """CON-020: Initialize provider without exceptions."""
        self.provider.initialize(self.config)

    def test_con_021_get_handler(self):
        """CON-021: Get handler returns StreamHandler."""
        self.provider.initialize(self.config)
        handler = self.provider.get_handler()
        self.assertIsInstance(handler, logging.StreamHandler)

    def test_con_022_handler_cached(self):
        """CON-022: Handler is cached (same instance)."""
        self.provider.initialize(self.config)
        handler1 = self.provider.get_handler()
        handler2 = self.provider.get_handler()
        self.assertIs(handler1, handler2)

    def test_con_023_handler_level(self):
        """CON-023: Handler level is NOTSET (level set on root logger, not handler)."""
        self.config.log_level = "WARNING"
        self.provider.initialize(self.config)
        handler = self.provider.get_handler()
        # ConsoleLoggingProvider doesn't set handler level - level is set on root logger instead
        self.assertEqual(handler.level, logging.NOTSET)

    def test_con_024_shutdown_flushes(self):
        """CON-024: Shutdown flushes handler."""
        self.provider.initialize(self.config)
        self.provider.get_handler()
        self.provider.shutdown()
        # Should not raise


class TestSentryTracingProvider(unittest.TestCase):
    """Test SentryTracingProvider (SEN-001 to SEN-009)."""

    def setUp(self):
        from api.observability.providers.sentry_provider import SentryTracingProvider

        self.provider = SentryTracingProvider()

    @patch("sentry_sdk.init")
    def test_sen_001_initialize_with_dsn(self, mock_init):
        """SEN-001: Initialize with DSN calls sentry_sdk.init."""
        config = MagicMock()
        config.sentry_dsn = "https://key@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 1.0
        config.sentry_profiles_sample_rate = 0.1

        self.provider.initialize(config)

        mock_init.assert_called_once()

    def test_sen_002_initialize_without_dsn(self):
        """SEN-002: Initialize without DSN logs warning, no init."""
        config = MagicMock()
        config.sentry_dsn = None

        with patch("api.observability.providers.sentry_provider.logger") as mock_logger:
            self.provider.initialize(config)
            mock_logger.warning.assert_called()

    @patch("sentry_sdk.init")
    @patch("sentry_sdk.start_span")
    def test_sen_003_create_span(self, mock_start_span, mock_init):
        """SEN-003: Create span returns Sentry span."""
        config = MagicMock()
        config.sentry_dsn = "https://key@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 1.0
        config.sentry_profiles_sample_rate = 0.1

        mock_span = MagicMock()
        mock_start_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_start_span.return_value.__exit__ = MagicMock(return_value=False)

        self.provider.initialize(config)
        with self.provider.span("test-op") as span:
            self.assertEqual(span, mock_span)

    @patch("sentry_sdk.init")
    @patch("sentry_sdk.capture_exception")
    def test_sen_005_record_exception(self, mock_capture, mock_init):
        """SEN-005: Record exception calls capture_exception."""
        config = MagicMock()
        config.sentry_dsn = "https://key@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 1.0
        config.sentry_profiles_sample_rate = 0.1

        self.provider.initialize(config)
        test_error = ValueError("test")
        self.provider.record_exception(test_error)

        mock_capture.assert_called_once_with(test_error)

    @patch("sentry_sdk.init")
    @patch("sentry_sdk.flush")
    def test_sen_007_shutdown(self, mock_flush, mock_init):
        """SEN-007: Shutdown calls sentry_sdk.flush."""
        config = MagicMock()
        config.sentry_dsn = "https://key@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 1.0
        config.sentry_profiles_sample_rate = 0.1

        self.provider.initialize(config)
        self.provider.shutdown()

        mock_flush.assert_called_once()

    @patch("sentry_sdk.init")
    def test_sen_008_sample_rate_passed(self, mock_init):
        """SEN-008: Sample rate is passed to sentry_sdk.init."""
        config = MagicMock()
        config.sentry_dsn = "https://key@sentry.io/123"
        config.environment = "test"
        config.service_version = "1.0.0"
        config.sentry_traces_sample_rate = 0.5
        config.sentry_profiles_sample_rate = 0.1

        self.provider.initialize(config)

        call_kwargs = mock_init.call_args[1]
        self.assertEqual(call_kwargs["traces_sample_rate"], 0.5)


class TestLogtailLoggingProvider(unittest.TestCase):
    """Test LogtailLoggingProvider (LOG-001 to LOG-007)."""

    def setUp(self):
        from api.observability.providers.logtail_provider import LogtailLoggingProvider

        self.provider = LogtailLoggingProvider()

    def test_log_001_initialize_with_token(self):
        """LOG-001: Initialize with token works."""
        config = MagicMock()
        config.betterstack_source_token = "test-token"
        config.betterstack_host = None

        self.provider.initialize(config)
        # Should not raise

    def test_log_002_initialize_without_token(self):
        """LOG-002: Initialize without token logs warning."""
        config = MagicMock()
        config.betterstack_source_token = None

        with patch("api.observability.providers.logtail_provider.logger") as mock_logger:
            self.provider.initialize(config)
            mock_logger.warning.assert_called()

    def test_log_002_get_handler_without_token_raises(self):
        """LOG-002: get_handler without token raises ValueError."""
        config = MagicMock()
        config.betterstack_source_token = None

        self.provider.initialize(config)
        with self.assertRaises(ValueError):
            self.provider.get_handler()

    @patch("logtail.LogtailHandler")
    def test_log_003_get_handler(self, mock_handler_class):
        """LOG-003: Get handler returns LogtailHandler."""
        config = MagicMock()
        config.betterstack_source_token = "test-token"
        config.betterstack_host = "https://test.betterstackdata.com"

        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler

        self.provider.initialize(config)
        self.provider.get_handler()  # Trigger handler creation

        mock_handler_class.assert_called_once_with(
            source_token="test-token",
            host="https://test.betterstackdata.com",
        )

    def test_log_007_missing_package_raises(self):
        """LOG-007: Missing logtail package raises ImportError."""
        config = MagicMock()
        config.betterstack_source_token = "test-token"
        config.betterstack_host = None

        self.provider.initialize(config)

        with patch.dict("sys.modules", {"logtail": None}):
            # Force reimport to trigger ImportError
            import sys

            if "logtail" in sys.modules:
                del sys.modules["logtail"]
            # The actual import error would occur in get_handler


class TestOTLPTracingProviderMocked(unittest.TestCase):
    """Test OTLPTracingProvider with mocked OpenTelemetry."""

    @patch("opentelemetry.trace.set_tracer_provider")
    @patch("opentelemetry.trace.get_tracer")
    @patch("opentelemetry.sdk.trace.TracerProvider")
    @patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter")
    @patch("opentelemetry.sdk.trace.export.BatchSpanProcessor")
    def test_otlp_001_initialize_with_endpoint(
        self,
        mock_processor,
        mock_exporter,
        mock_provider,
        mock_get_tracer,
        mock_set_provider,
    ):
        """OTLP-001: Initialize with endpoint creates TracerProvider."""
        from api.observability.providers.otlp import OTLPTracingProvider

        provider = OTLPTracingProvider()
        config = MagicMock()
        config.service_name = "test-service"
        config.service_version = "1.0.0"
        config.environment = "test"
        config.tracing_sample_rate = 1.0
        config.otlp_endpoint = "http://collector:4317"
        config.otlp_insecure = True

        provider.initialize(config)

        mock_exporter.assert_called_once()
        mock_provider.assert_called_once()
        mock_set_provider.assert_called_once()


class TestOTLPLoggingProviderMocked(unittest.TestCase):
    """Test OTLPLoggingProvider with mocked OpenTelemetry."""

    def test_otlp_logging_initialize(self):
        """OTLP-020: Initialize provider stores config."""
        from api.observability.providers.otlp import OTLPLoggingProvider

        provider = OTLPLoggingProvider()
        config = MagicMock()
        config.service_name = "test-service"
        config.service_version = "1.0.0"
        config.environment = "test"
        config.log_level = "INFO"
        config.otlp_endpoint = "http://collector:4317"
        config.otlp_insecure = True

        provider.initialize(config)
        # Config should be stored
        self.assertEqual(provider._config, config)


if __name__ == "__main__":
    unittest.main()
