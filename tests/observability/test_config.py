import unittest
from unittest.mock import patch

from api.observability.config import LoggingBackend, ObservabilitySettings, TracingBackend


class TestConfigDefaults(unittest.TestCase):
    """Test default configuration values (CFG-001 to CFG-003)."""

    def test_cfg_001_no_env_vars_uses_defaults(self):
        """CFG-001: No environment variables set uses defaults."""
        with patch.dict("os.environ", {}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.CONSOLE)
            self.assertEqual(settings.logging_backends, [LoggingBackend.CONSOLE])
            self.assertEqual(settings.tracing_sample_rate, 1.0)
            self.assertEqual(settings.log_level, "INFO")

    def test_cfg_002_service_name_only(self):
        """CFG-002: Only OTEL_SERVICE_NAME set, other defaults apply."""
        with patch.dict("os.environ", {"OTEL_SERVICE_NAME": "my-service"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.service_name, "my-service")
            self.assertEqual(settings.tracing_backend, TracingBackend.CONSOLE)

    def test_cfg_003_empty_logging_backend_defaults_to_console(self):
        """CFG-003: Empty OTEL_LOGGING_BACKEND falls back to console."""
        with patch.dict("os.environ", {"OTEL_LOGGING_BACKEND": ""}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.logging_backends, [LoggingBackend.CONSOLE])


class TestTracingBackendSelection(unittest.TestCase):
    """Test tracing backend selection (CFG-010 to CFG-016)."""

    def test_cfg_010_console_backend(self):
        """CFG-010: Console backend selection."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "console"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.CONSOLE)

    def test_cfg_011_otlp_backend(self):
        """CFG-011: OTLP backend selection."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "otlp"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.OTLP)

    def test_cfg_013_sentry_backend(self):
        """CFG-013: Sentry backend selection."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "sentry"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.SENTRY)

    def test_cfg_014_none_backend(self):
        """CFG-014: None backend (tracing disabled)."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "none"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.NONE)

    def test_cfg_015_invalid_backend_falls_back_to_console(self):
        """CFG-015: Invalid backend falls back to console (graceful degradation)."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "invalid_backend"}, clear=True):
            settings = ObservabilitySettings()
            # Implementation gracefully falls back to console for invalid backends
            self.assertEqual(settings.tracing_backend, TracingBackend.CONSOLE)

    def test_cfg_016_case_insensitive_backend(self):
        """CFG-016: Backend selection is case insensitive."""
        with patch.dict("os.environ", {"OTEL_TRACING_BACKEND": "OTLP"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_backend, TracingBackend.OTLP)


class TestLoggingBackendSelection(unittest.TestCase):
    """Test logging backend selection (CFG-020 to CFG-024)."""

    def test_cfg_020_single_backend(self):
        """CFG-020: Single logging backend."""
        with patch.dict("os.environ", {"OTEL_LOGGING_BACKEND": "console"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.logging_backends, [LoggingBackend.CONSOLE])

    def test_cfg_021_multiple_backends(self):
        """CFG-021: Multiple logging backends (comma-separated)."""
        with patch.dict("os.environ", {"OTEL_LOGGING_BACKEND": "console,logtail"}, clear=True):
            settings = ObservabilitySettings()
            self.assertIn(LoggingBackend.CONSOLE, settings.logging_backends)
            self.assertIn(LoggingBackend.LOGTAIL, settings.logging_backends)

    def test_cfg_022_backends_with_spaces(self):
        """CFG-022: Backends with spaces trimmed."""
        with patch.dict("os.environ", {"OTEL_LOGGING_BACKEND": "console, otlp"}, clear=True):
            settings = ObservabilitySettings()
            self.assertIn(LoggingBackend.CONSOLE, settings.logging_backends)
            self.assertIn(LoggingBackend.OTLP, settings.logging_backends)

    def test_cfg_023_duplicate_backends_allowed(self):
        """CFG-023: Duplicate backends are allowed (not deduplicated)."""
        with patch.dict("os.environ", {"OTEL_LOGGING_BACKEND": "console,console"}, clear=True):
            settings = ObservabilitySettings()
            # Implementation allows duplicates - each entry is added
            console_count = settings.logging_backends.count(LoggingBackend.CONSOLE)
            self.assertEqual(console_count, 2)


class TestSampleRateValidation(unittest.TestCase):
    """Test sample rate validation (CFG-030 to CFG-034)."""

    def test_cfg_030_valid_sample_rate(self):
        """CFG-030: Valid sample rate (0.5)."""
        with patch.dict("os.environ", {"OTEL_TRACING_SAMPLE_RATE": "0.5"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 0.5)

    def test_cfg_031_sample_rate_above_1_clamped(self):
        """CFG-031: Sample rate > 1.0 clamped to 1.0."""
        with patch.dict("os.environ", {"OTEL_TRACING_SAMPLE_RATE": "1.5"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 1.0)

    def test_cfg_032_sample_rate_below_0_clamped(self):
        """CFG-032: Sample rate < 0.0 clamped to 0.0."""
        with patch.dict("os.environ", {"OTEL_TRACING_SAMPLE_RATE": "-0.5"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 0.0)

    def test_cfg_034_zero_sample_rate(self):
        """CFG-034: Zero sample rate (no sampling)."""
        with patch.dict("os.environ", {"OTEL_TRACING_SAMPLE_RATE": "0"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.tracing_sample_rate, 0.0)


class TestProviderSpecificConfig(unittest.TestCase):
    """Test provider-specific configuration (CFG-040 to CFG-071)."""

    def test_cfg_040_otlp_endpoint(self):
        """CFG-040: OTLP endpoint configuration."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "otlp",
                "OTEL_OTLP_ENDPOINT": "http://collector:4317",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.otlp_endpoint, "http://collector:4317")

    def test_cfg_041_otlp_insecure(self):
        """CFG-041: OTLP insecure flag."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "otlp",
                "OTEL_OTLP_INSECURE": "true",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertTrue(settings.otlp_insecure)

    def test_cfg_060_sentry_dsn(self):
        """CFG-060: Sentry DSN configuration."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "sentry",
                "SENTRY_DSN": "https://key@sentry.io/123",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.sentry_dsn, "https://key@sentry.io/123")

    def test_cfg_061_sentry_sample_rates(self):
        """CFG-061: Sentry sample rates."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_TRACING_BACKEND": "sentry",
                "SENTRY_TRACES_SAMPLE_RATE": "0.5",
                "SENTRY_PROFILES_SAMPLE_RATE": "0.1",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.sentry_traces_sample_rate, 0.5)
            self.assertEqual(settings.sentry_profiles_sample_rate, 0.1)

    def test_cfg_070_logtail_token(self):
        """CFG-070: Logtail/Better Stack token."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_LOGGING_BACKEND": "logtail",
                "BETTERSTACK_SOURCE_TOKEN": "test-token-123",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.betterstack_source_token, "test-token-123")

    def test_cfg_071_logtail_host(self):
        """CFG-071: Logtail/Better Stack host."""
        with patch.dict(
            "os.environ",
            {
                "OTEL_LOGGING_BACKEND": "logtail",
                "BETTERSTACK_HOST": "https://custom.betterstackdata.com",
            },
            clear=True,
        ):
            settings = ObservabilitySettings()
            self.assertEqual(settings.betterstack_host, "https://custom.betterstackdata.com")


class TestEnvironmentAndVersion(unittest.TestCase):
    """Test environment and version configuration."""

    def test_environment_setting(self):
        """Test OTEL_ENVIRONMENT setting."""
        with patch.dict("os.environ", {"OTEL_ENVIRONMENT": "production"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.environment, "production")

    def test_service_version_setting(self):
        """Test OTEL_SERVICE_VERSION setting."""
        with patch.dict("os.environ", {"OTEL_SERVICE_VERSION": "2.0.0"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.service_version, "2.0.0")

    def test_log_level_setting(self):
        """Test OTEL_LOG_LEVEL setting."""
        with patch.dict("os.environ", {"OTEL_LOG_LEVEL": "DEBUG"}, clear=True):
            settings = ObservabilitySettings()
            self.assertEqual(settings.log_level, "DEBUG")


if __name__ == "__main__":
    unittest.main()
