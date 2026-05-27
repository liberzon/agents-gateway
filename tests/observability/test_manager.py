import unittest
from unittest.mock import MagicMock, patch

from api.observability.config import ObservabilitySettings


class TestObservabilityManagerInitialization(unittest.TestCase):
    """Test ObservabilityManager initialization (MGR-001 to MGR-007)."""

    def setUp(self):
        """Reset singleton state before each test."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def tearDown(self):
        """Reset singleton state after each test."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def test_mgr_001_initialize_with_console(self):
        """MGR-001: Initialize with console backend."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",  # Disable test mode
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            self.assertTrue(manager.is_initialized)
            self.assertIsNotNone(manager._tracing_provider)
            self.assertEqual(len(manager._logging_providers), 1)

    def test_mgr_002_initialize_with_otlp(self):
        """MGR-002: Initialize with OTLP backend (mocked)."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "otlp",
                "OTEL_LOGGING_BACKEND": "console",
                "OTEL_OTLP_ENDPOINT": "http://collector:4317",
                "TESTING": "false",
            },
            clear=True,
        ):
            # Mock OTLP provider at its source location
            with patch("api.observability.providers.otlp.OTLPTracingProvider") as mock_otlp:
                mock_provider = MagicMock()
                mock_otlp.return_value = mock_provider

                manager = ObservabilityManager.get_instance()
                config = ObservabilitySettings()
                manager.initialize(config)

                self.assertTrue(manager.is_initialized)
                mock_provider.initialize.assert_called_once()

    def test_mgr_004_initialize_with_sentry(self):
        """MGR-004: Initialize with Sentry backend (mocked)."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "sentry",
                "SENTRY_DSN": "https://key@sentry.io/123",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            with patch("api.observability.providers.sentry_provider.SentryTracingProvider") as mock_sentry:
                mock_provider = MagicMock()
                mock_sentry.return_value = mock_provider

                manager = ObservabilityManager.get_instance()
                config = ObservabilitySettings()
                manager.initialize(config)

                self.assertTrue(manager.is_initialized)
                mock_provider.initialize.assert_called_once()

    def test_mgr_005_initialize_multiple_loggers(self):
        """MGR-005: Initialize with multiple logging backends."""
        import logging

        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console,logtail",
                "BETTERSTACK_SOURCE_TOKEN": "test-token",
                "TESTING": "false",
            },
            clear=True,
        ):
            with patch("api.observability.providers.logtail_provider.LogtailLoggingProvider") as mock_logtail:
                mock_provider = MagicMock()
                # Create a real handler for the mock to return
                mock_handler = logging.NullHandler()
                mock_provider.get_handler.return_value = mock_handler
                mock_logtail.return_value = mock_provider

                manager = ObservabilityManager.get_instance()
                config = ObservabilitySettings()
                manager.initialize(config)

                self.assertEqual(len(manager._logging_providers), 2)

    def test_mgr_006_double_initialization_idempotent(self):
        """MGR-006: Double initialization is idempotent."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)
            first_provider = manager._tracing_provider

            manager.initialize(config)
            second_provider = manager._tracing_provider

            self.assertIs(first_provider, second_provider)

    def test_mgr_007_initialize_none_tracing(self):
        """MGR-007: Initialize with none tracing backend."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "none",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            self.assertTrue(manager.is_initialized)
            self.assertIsNone(manager._tracing_provider)


class TestObservabilityManagerTracing(unittest.TestCase):
    """Test ObservabilityManager tracing operations (MGR-010 to MGR-015)."""

    def setUp(self):
        """Reset and initialize with console backend."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            config = ObservabilitySettings()
            manager = ObservabilityManager.get_instance()
            manager.initialize(config)
            self.manager = manager

    def tearDown(self):
        """Reset singleton state after each test."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def test_mgr_010_span_initialized(self):
        """MGR-010: Create span when initialized."""
        with self.manager.span("test-span") as span:
            # Console provider returns None
            self.assertIsNone(span)

    def test_mgr_011_span_not_initialized(self):
        """MGR-011: Span returns None when not initialized."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()
        manager = ObservabilityManager.get_instance()
        # Not initialized

        with manager.span("test-span") as span:
            self.assertIsNone(span)

    def test_mgr_012_span_with_attributes(self):
        """MGR-012: Span with attributes passes them through."""
        with self.manager.span("test-span", {"key": "value"}) as span:
            self.assertIsNone(span)  # Console returns None

    def test_mgr_013_record_exception(self):
        """MGR-013: Record exception delegates to provider."""
        self.manager.record_exception(ValueError("test"))
        # Should not raise

    def test_mgr_014_get_trace_id(self):
        """MGR-014: Get trace ID returns provider's trace ID."""
        trace_id = self.manager.get_current_trace_id()
        self.assertIsNone(trace_id)  # Console returns None

    def test_mgr_015_get_span_id(self):
        """MGR-015: Get span ID returns provider's span ID."""
        span_id = self.manager.get_current_span_id()
        self.assertIsNone(span_id)  # Console returns None


class TestObservabilityManagerShutdown(unittest.TestCase):
    """Test ObservabilityManager shutdown (MGR-030 to MGR-033)."""

    def setUp(self):
        """Reset singleton state."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def tearDown(self):
        """Reset singleton state after each test."""
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def test_mgr_030_shutdown_tracing(self):
        """MGR-030: Shutdown calls tracing provider shutdown."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            # Mock the provider's shutdown using patch.object
            with patch.object(manager._tracing_provider, "shutdown") as mock_shutdown:
                manager.shutdown()
                mock_shutdown.assert_called_once()

    def test_mgr_031_shutdown_logging(self):
        """MGR-031: Shutdown calls all logging provider shutdowns."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            # Mock the provider's shutdown using patch.object
            with patch.object(manager._logging_providers[0], "shutdown") as mock_shutdown:
                manager.shutdown()
                mock_shutdown.assert_called_once()

    def test_mgr_032_shutdown_before_init(self):
        """MGR-032: Shutdown before init is no-op."""
        from api.observability import ObservabilityManager

        manager = ObservabilityManager.get_instance()
        manager.shutdown()
        # Should not raise

    def test_mgr_033_double_shutdown(self):
        """MGR-033: Double shutdown is idempotent."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "OTEL_LOGGING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            manager.shutdown()
            manager.shutdown()
            # Should not raise


class TestObservabilityManagerIsInitialized(unittest.TestCase):
    """Test is_initialized property."""

    def setUp(self):
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def tearDown(self):
        from api.observability import ObservabilityManager

        ObservabilityManager.reset_instance()

    def test_is_initialized_false_initially(self):
        """is_initialized is False before initialization."""
        from api.observability import ObservabilityManager

        manager = ObservabilityManager.get_instance()
        self.assertFalse(manager.is_initialized)

    def test_is_initialized_true_after_init(self):
        """is_initialized is True after initialization."""
        from api.observability import ObservabilityManager

        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "console",
                "TESTING": "false",
            },
            clear=True,
        ):
            manager = ObservabilityManager.get_instance()
            config = ObservabilitySettings()
            manager.initialize(config)

            self.assertTrue(manager.is_initialized)


if __name__ == "__main__":
    unittest.main()
