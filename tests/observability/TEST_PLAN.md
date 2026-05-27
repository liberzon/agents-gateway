# Observability Module - Comprehensive Test Plan

## 1. Overview

This test plan covers the pluggable observability module (`api/observability/`) which provides vendor-neutral tracing and logging using OpenTelemetry standards.

### 1.1 Scope

| Component | Description | Priority |
|-----------|-------------|----------|
| `config.py` | Configuration settings (ObservabilitySettings) | High |
| `providers/base.py` | Abstract provider interfaces | High |
| `providers/console.py` | Console provider (default) | High |
| `providers/otlp.py` | OTLP tracing and logging | High |
| `providers/sentry_provider.py` | Sentry bridge (legacy) | Medium |
| `providers/logtail_provider.py` | Logtail/Better Stack bridge (legacy) | Medium |
| `instrumentation.py` | Auto-instrumentation setup | Medium |
| `__init__.py` | ObservabilityManager orchestrator | High |

### 1.2 Test Types

- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: Provider initialization with real SDK calls (mocked network)
- **Configuration Tests**: Environment variable parsing and validation
- **Error Handling Tests**: Graceful degradation scenarios
- **Compatibility Tests**: Backward compatibility with legacy env vars

---

## 2. Configuration Tests (`config.py`)

### 2.1 Default Values

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| CFG-001 | No environment variables set | Defaults: tracing=console, logging=[console], sample_rate=1.0 |
| CFG-002 | Only OTEL_SERVICE_NAME set | Uses provided name, other defaults apply |
| CFG-003 | Empty OTEL_LOGGING_BACKEND | Falls back to console |

### 2.2 Tracing Backend Selection

| Test ID | Test Case | Input | Expected |
|---------|-----------|-------|----------|
| CFG-010 | Console backend | `OTEL_TRACING_BACKEND=console` | TracingBackend.CONSOLE |
| CFG-011 | OTLP backend | `OTEL_TRACING_BACKEND=otlp` | TracingBackend.OTLP |
| CFG-012 | Jaeger backend | `OTEL_TRACING_BACKEND=jaeger` | TracingBackend.JAEGER |
| CFG-013 | Sentry backend | `OTEL_TRACING_BACKEND=sentry` | TracingBackend.SENTRY |
| CFG-014 | None backend | `OTEL_TRACING_BACKEND=none` | TracingBackend.NONE |
| CFG-015 | Invalid backend | `OTEL_TRACING_BACKEND=invalid` | ValidationError or fallback |
| CFG-016 | Case insensitive | `OTEL_TRACING_BACKEND=OTLP` | TracingBackend.OTLP |

### 2.3 Logging Backend Selection

| Test ID | Test Case | Input | Expected |
|---------|-----------|-------|----------|
| CFG-020 | Single backend | `OTEL_LOGGING_BACKEND=console` | [LoggingBackend.CONSOLE] |
| CFG-021 | Multiple backends | `OTEL_LOGGING_BACKEND=console,logtail` | [CONSOLE, LOGTAIL] |
| CFG-022 | With spaces | `OTEL_LOGGING_BACKEND=console, otlp` | [CONSOLE, OTLP] |
| CFG-023 | Duplicate backends | `OTEL_LOGGING_BACKEND=console,console` | [CONSOLE] (deduplicated) |
| CFG-024 | Empty string | `OTEL_LOGGING_BACKEND=` | [CONSOLE] (default) |

### 2.4 Sample Rate Validation

| Test ID | Test Case | Input | Expected |
|---------|-----------|-------|----------|
| CFG-030 | Valid rate | `OTEL_TRACING_SAMPLE_RATE=0.5` | 0.5 |
| CFG-031 | Rate > 1.0 | `OTEL_TRACING_SAMPLE_RATE=1.5` | Clamped to 1.0 |
| CFG-032 | Rate < 0.0 | `OTEL_TRACING_SAMPLE_RATE=-0.5` | Clamped to 0.0 |
| CFG-033 | Non-numeric | `OTEL_TRACING_SAMPLE_RATE=high` | ValidationError or default |
| CFG-034 | Zero rate | `OTEL_TRACING_SAMPLE_RATE=0` | 0.0 (no sampling) |

### 2.5 Provider-Specific Configuration

| Test ID | Test Case | Env Vars | Expected |
|---------|-----------|----------|----------|
| CFG-040 | OTLP endpoint | `OTEL_OTLP_ENDPOINT=http://collector:4317` | endpoint set |
| CFG-041 | OTLP insecure | `OTEL_OTLP_INSECURE=true` | insecure=True |
| CFG-042 | OTLP default endpoint | No OTEL_OTLP_ENDPOINT | localhost:4317 |
| CFG-050 | Jaeger host | `OTEL_JAEGER_AGENT_HOST=jaeger.local` | host set |
| CFG-051 | Jaeger port | `OTEL_JAEGER_AGENT_PORT=6832` | port=6832 |
| CFG-052 | Jaeger defaults | No Jaeger vars | localhost:6831 |
| CFG-060 | Sentry DSN | `SENTRY_DSN=https://...` | dsn set |
| CFG-061 | Sentry sample rates | `SENTRY_TRACES_SAMPLE_RATE=0.5` | rate=0.5 |
| CFG-070 | Logtail token | `BETTERSTACK_SOURCE_TOKEN=xxx` | token set |
| CFG-071 | Logtail host | `BETTERSTACK_HOST=https://...` | host set |

### 2.6 Backward Compatibility

| Test ID | Test Case | Legacy Vars | Expected |
|---------|-----------|-------------|----------|
| CFG-080 | Sentry DSN alone triggers Sentry | `SENTRY_DSN=xxx` (no OTEL_TRACING_BACKEND) | Auto-select Sentry? |
| CFG-081 | Logtail token alone triggers Logtail | `BETTERSTACK_SOURCE_TOKEN=xxx` | Auto-add to logging? |

---

## 3. Provider Unit Tests

### 3.1 Console Tracing Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| CON-001 | Initialize provider | No exceptions |
| CON-002 | Create span (initialized) | Returns None (no-op) |
| CON-003 | Create span (not initialized) | Returns None |
| CON-004 | Span with attributes | Logs attributes, returns None |
| CON-005 | Nested spans | Works correctly |
| CON-006 | Record exception | Logs exception |
| CON-007 | Get trace ID | Returns None |
| CON-008 | Get span ID | Returns None |
| CON-009 | Shutdown | No exceptions |
| CON-010 | Double initialization | Idempotent |

### 3.2 Console Logging Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| CON-020 | Initialize provider | No exceptions |
| CON-021 | Get handler | Returns StreamHandler |
| CON-022 | Handler cached | Same instance returned |
| CON-023 | Handler level | Matches config log_level |
| CON-024 | Shutdown flushes | Handler flushed |

### 3.3 OTLP Tracing Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| OTLP-001 | Initialize with endpoint | TracerProvider created |
| OTLP-002 | Initialize without endpoint | Uses default localhost:4317 |
| OTLP-003 | Create span | Returns OTel Span object |
| OTLP-004 | Span attributes | Attributes attached to span |
| OTLP-005 | Record exception | Exception recorded in span |
| OTLP-006 | Get trace ID | Returns 32-char hex string |
| OTLP-007 | Get span ID | Returns 16-char hex string |
| OTLP-008 | Shutdown | Provider shutdown called |
| OTLP-009 | Missing packages | Raises ImportError with message |
| OTLP-010 | Connection error | Graceful degradation |

### 3.4 OTLP Logging Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| OTLP-020 | Initialize provider | LoggerProvider created |
| OTLP-021 | Get handler | Returns LoggingHandler |
| OTLP-022 | Handler level | Matches config |
| OTLP-023 | Shutdown | Flushes logs |
| OTLP-024 | Missing packages | Raises ImportError |

### 3.5 Jaeger Tracing Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| JAE-001 | Initialize with host/port | JaegerExporter created |
| JAE-002 | Initialize with defaults | Uses localhost:6831 |
| JAE-003 | Create span | Returns OTel Span |
| JAE-004 | Record exception | Exception in span |
| JAE-005 | Get trace/span IDs | Returns hex strings |
| JAE-006 | Shutdown | Exporter flushed |
| JAE-007 | Missing packages | Raises ImportError |

### 3.6 Sentry Tracing Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| SEN-001 | Initialize with DSN | sentry_sdk.init called |
| SEN-002 | Initialize without DSN | Warning logged, no init |
| SEN-003 | Create span | Sentry transaction span |
| SEN-004 | Span attributes | Data attached to span |
| SEN-005 | Record exception | capture_exception called |
| SEN-006 | Get trace ID | Returns Sentry trace ID |
| SEN-007 | Shutdown | sentry_sdk.flush called |
| SEN-008 | Sample rate passed | traces_sample_rate set |
| SEN-009 | Profiles sample rate | profile_session_sample_rate set |

### 3.7 Logtail Logging Provider

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| LOG-001 | Initialize with token | LogtailHandler created |
| LOG-002 | Initialize without token | ValueError on get_handler |
| LOG-003 | Get handler | Returns LogtailHandler |
| LOG-004 | JSON formatter | Logs formatted as JSON |
| LOG-005 | Trace context injection | trace_id/span_id in logs |
| LOG-006 | Shutdown | Handler flushed |
| LOG-007 | Missing package | Raises ImportError |

---

## 4. ObservabilityManager Tests

### 4.1 Initialization

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| MGR-001 | Initialize with console | Both providers initialized |
| MGR-002 | Initialize with OTLP | OTLP providers created |
| MGR-003 | Initialize with Jaeger | Jaeger tracing + console logging |
| MGR-004 | Initialize with Sentry | Sentry tracing provider |
| MGR-005 | Initialize with multiple loggers | All logging providers active |
| MGR-006 | Double initialization | Idempotent (no-op second time) |
| MGR-007 | Initialize with none tracing | No tracing provider |

### 4.2 Tracing Operations

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| MGR-010 | Create span (initialized) | Delegates to provider |
| MGR-011 | Create span (not initialized) | Returns None |
| MGR-012 | Span with attributes | Attributes passed through |
| MGR-013 | Record exception | Delegates to provider |
| MGR-014 | Get trace ID | Returns provider's trace ID |
| MGR-015 | Get span ID | Returns provider's span ID |

### 4.3 Logging Operations

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| MGR-020 | Configure root logger | Handlers attached |
| MGR-021 | Multiple logging providers | All handlers attached |
| MGR-022 | Log level propagation | All handlers respect level |

### 4.4 Shutdown

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| MGR-030 | Shutdown tracing | Provider shutdown called |
| MGR-031 | Shutdown logging | All handlers flushed |
| MGR-032 | Shutdown before init | No-op, no exceptions |
| MGR-033 | Double shutdown | Idempotent |

---

## 5. Auto-Instrumentation Tests

### 5.1 FastAPI Instrumentation

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INS-001 | OTLP backend | FastAPIInstrumentor called |
| INS-002 | Jaeger backend | FastAPIInstrumentor called |
| INS-003 | Console backend | Instrumentation skipped |
| INS-004 | Sentry backend | Instrumentation skipped |
| INS-005 | Missing package | Warning logged, continues |

### 5.2 HTTPX Instrumentation

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INS-010 | OTLP backend | HTTPXClientInstrumentor called |
| INS-011 | Missing package | Warning logged, continues |

### 5.3 SQLAlchemy Instrumentation

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INS-020 | OTLP backend | SQLAlchemyInstrumentor called |
| INS-021 | Engine passed | Instrumented with engine |
| INS-022 | Missing package | Warning logged, continues |

### 5.4 Uninstrumentation

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INS-030 | Uninstrument all | All instrumentors removed |
| INS-031 | Partial uninstrument | Only available ones removed |

---

## 6. Integration Tests

### 6.1 Full Stack Initialization

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INT-001 | Console tracing + console logging | Both work |
| INT-002 | OTLP tracing + OTLP logging | Both export |
| INT-003 | Jaeger tracing + console logging | Mixed works |
| INT-004 | Sentry tracing + Logtail logging | Legacy combo works |
| INT-005 | Multiple logging backends | All receive logs |

### 6.2 Application Lifecycle

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INT-010 | App startup | Observability initialized |
| INT-011 | Request tracing | Spans created for requests |
| INT-012 | App shutdown | Providers cleaned up |
| INT-013 | Graceful shutdown | Pending spans/logs flushed |

### 6.3 Error Scenarios

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| INT-020 | OTLP collector unavailable | App still starts |
| INT-021 | Jaeger agent unavailable | App still starts |
| INT-022 | Invalid Sentry DSN | Warning logged, continues |
| INT-023 | Invalid Logtail token | Warning logged, continues |

---

## 7. Error Handling Tests

### 7.1 Missing Dependencies

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| ERR-001 | OTLP without otel packages | ImportError with install instructions |
| ERR-002 | Jaeger without jaeger package | ImportError with install instructions |
| ERR-003 | Logtail without logtail package | ImportError with install instructions |
| ERR-004 | Sentry without sentry-sdk | ImportError with install instructions |

### 7.2 Runtime Errors

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| ERR-010 | Provider init fails | Error logged, graceful continue |
| ERR-011 | Span creation fails | Returns None, error logged |
| ERR-012 | Exception recording fails | Error logged, no crash |
| ERR-013 | Shutdown fails | Error logged, continues |

### 7.3 Configuration Errors

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| ERR-020 | Invalid backend enum | ValidationError |
| ERR-021 | Invalid log level | ValidationError or default |
| ERR-022 | Malformed endpoint URL | Warning logged |

---

## 8. Performance Tests

### 8.1 Overhead Measurement

| Test ID | Test Case | Acceptance Criteria |
|---------|-----------|---------------------|
| PERF-001 | Console provider overhead | < 1ms per span |
| PERF-002 | OTLP batch export | Async, non-blocking |
| PERF-003 | High-frequency spans | No memory leaks |
| PERF-004 | Large attributes | Handles gracefully |

### 8.2 Sampling Behavior

| Test ID | Test Case | Expected |
|---------|-----------|----------|
| PERF-010 | 0% sample rate | No spans exported |
| PERF-011 | 50% sample rate | ~50% spans exported |
| PERF-012 | 100% sample rate | All spans exported |

---

## 9. Test Environment

### 9.1 Required Setup

```bash
# Install test dependencies
uv pip install pytest pytest-cov pytest-asyncio

# Install optional providers for full testing
uv pip install opentelemetry-api opentelemetry-sdk
uv pip install opentelemetry-exporter-otlp
uv pip install opentelemetry-exporter-jaeger
uv pip install sentry-sdk
uv pip install logtail-python
```

### 9.2 Mock Services (Optional)

For integration tests with real network calls:

```yaml
# docker-compose.test.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"
      - "16686:16686"

  otel-collector:
    image: otel/opentelemetry-collector:latest
    ports:
      - "4317:4317"
```

---

## 10. Test Execution

### 10.1 Run All Observability Tests

```bash
# Unit tests only
pytest tests/observability/ -v

# With coverage
pytest tests/observability/ --cov=api/observability --cov-report=html

# Specific test class
pytest tests/observability/test_providers.py::TestOTLPTracingProvider -v
```

### 10.2 Run by Category

```bash
# Configuration tests
pytest tests/observability/ -k "config" -v

# Provider tests
pytest tests/observability/ -k "provider" -v

# Integration tests
pytest tests/observability/ -k "integration" -v
```

### 10.3 CI/CD Integration

```yaml
# .github/workflows/test-observability.yml
- name: Test Observability Module
  run: |
    pytest tests/observability/ \
      --cov=api/observability \
      --cov-fail-under=80 \
      --junitxml=test-results/observability.xml
```

---

## 11. Coverage Requirements

| Component | Minimum Coverage |
|-----------|-----------------|
| `config.py` | 90% |
| `providers/base.py` | 100% |
| `providers/console.py` | 95% |
| `providers/otlp.py` | 85% |
| `providers/jaeger.py` | 85% |
| `providers/sentry_provider.py` | 80% |
| `providers/logtail_provider.py` | 80% |
| `instrumentation.py` | 75% |
| `__init__.py` | 90% |

**Overall Target**: 85% line coverage

---

## 12. Test Data

### 12.1 Environment Variable Sets

```python
# Development (default)
ENV_DEV = {}

# Production with Sentry
ENV_SENTRY = {
    "OTEL_TRACING_BACKEND": "sentry",
    "OTEL_LOGGING_BACKEND": "console,logtail",
    "SENTRY_DSN": "https://key@sentry.io/123",
    "BETTERSTACK_SOURCE_TOKEN": "test-token",
}

# Cloud-native OTLP
ENV_OTLP = {
    "OTEL_TRACING_BACKEND": "otlp",
    "OTEL_LOGGING_BACKEND": "otlp",
    "OTEL_OTLP_ENDPOINT": "http://collector:4317",
}

# Self-hosted Jaeger
ENV_JAEGER = {
    "OTEL_TRACING_BACKEND": "jaeger",
    "OTEL_JAEGER_AGENT_HOST": "jaeger.internal",
    "OTEL_JAEGER_AGENT_PORT": "6831",
}
```

### 12.2 Sample Span Attributes

```python
SAMPLE_ATTRIBUTES = {
    "user.id": "user-123",
    "request.method": "POST",
    "request.path": "/v2/agents/chat",
    "agent.id": "assistant-v1",
    "http.status_code": 200,
}
```

---

## 13. Known Limitations

1. **OpenTelemetry Global State**: OTel uses global tracer/logger providers; tests must reset state between runs
2. **Sentry SDK Global**: Sentry SDK is global; mock `sentry_sdk.init` to avoid side effects
3. **Network Dependencies**: OTLP/Jaeger tests should mock network calls unless integration testing
4. **Async Testing**: Some providers may have async components requiring `pytest-asyncio`

---

## 14. Future Enhancements

- [ ] Add metrics provider support (deferred from current scope)
- [ ] Add Prometheus metrics exporter
- [ ] Add distributed trace context propagation tests
- [ ] Add load testing for high-throughput scenarios
- [ ] Add multi-process/multi-worker tests