"""OpenTelemetry setup — ALL telemetry configuration lives in this one module.

Three signals (traces, metrics, logs) export over OTLP/HTTP. WHERE they go is
pure env-var configuration; the code is identical for local Jaeger and Grafana
Cloud — swapping backends is a config-only change:

    OTEL_EXPORTER_OTLP_ENDPOINT   http://localhost:4318                (Jaeger)
                                  https://otlp-gateway-<zone>.grafana.net/otlp
                                                                  (Grafana Cloud)
    OTEL_EXPORTER_OTLP_HEADERS    Grafana Cloud auth, exactly as its setup UI
                                  generates it:
                                  Authorization=Basic <base64(instanceID:token)>
    DEPLOYMENT_ENVIRONMENT        local | production   (resource attribute)

Telemetry is a NO-OP when OTEL_EXPORTER_OTLP_ENDPOINT is unset: providers are
never installed, manual spans in the services become free no-ops, and only the
structured JSON logging to stdout remains active.

Sentry is deliberately untouched — it stays the error-alerting tool; these
signals are for performance investigation.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from .config import ENV_FILE

# The OTEL_* vars are read from the PROCESS environment — by this module and
# by the OTLP exporters themselves — but pydantic-settings loads backend/.env
# only into the Settings object, never into os.environ. Bridge that here.
# load_dotenv never overrides variables already set in the real environment,
# so Render (which injects real env vars) is unaffected.
load_dotenv(ENV_FILE)

# Opt in to the STABLE http semantic conventions (metric
# http.server.request.duration in seconds, attributes http.route /
# http.request.method / http.response.status_code). Must be set before any
# instrumentation package is imported, which is why imports happen inside
# setup_telemetry().
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

from opentelemetry import trace  # noqa: E402  (API only — safe before opt-in)

# Render sets RENDER_GIT_COMMIT on every deploy; locally we fall back to "dev".
APP_VERSION = os.getenv("RENDER_GIT_COMMIT", "")[:7] or "dev"

# Flipped to True at the end of setup_telemetry(); surfaced in /health so you
# can tell from the public endpoint whether the deployed process is exporting
# (Render's free-tier logs make the startup line hard to retrieve).
OTEL_ACTIVE = False

# Process boot time — used for /health uptime and cold-start span attributes.
# Render's free tier spins the instance down when idle; the first request after
# a spin-up pays a large cold-start penalty that would silently pollute every
# latency percentile. Tagging spans lets dashboards isolate or exclude them.
_process_start_monotonic = time.monotonic()
_served_first_request = False

logger = logging.getLogger(__name__)


def seconds_since_boot() -> float:
    return round(time.monotonic() - _process_start_monotonic, 3)


def _server_request_hook(span, scope) -> None:
    """Runs at the start of every request span (FastAPI auto-instrumentation)."""
    global _served_first_request
    if span is None or not span.is_recording():
        return
    cold = not _served_first_request
    _served_first_request = True
    span.set_attribute("app.cold_start", cold)
    span.set_attribute("app.seconds_since_boot", seconds_since_boot())


class JsonLogFormatter(logging.Formatter):
    """Structured JSON logs, one object per line, carrying the active trace
    context so any log line can be joined to its trace in Tempo/Loki (and
    vice versa via Grafana's trace-to-logs correlation)."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            entry["trace_id"] = format(ctx.trace_id, "032x")
            entry["span_id"] = format(ctx.span_id, "016x")
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def _setup_json_logging() -> None:
    """Structured stdout logging — always on, even with OTLP export disabled
    (Render captures stdout, so prod logs are searchable JSON either way)."""
    formatter = JsonLogFormatter()
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(formatter)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    # Uvicorn installs its own handlers before importing the app; reformat them
    # so access/error lines are JSON too instead of plain text.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)


def setup_telemetry(app) -> None:
    """Configure logging always, and the full OTel pipeline when an OTLP
    endpoint is configured. Must run BEFORE the routers are imported so the
    SQLAlchemy engine (created at app.db import time) is instrumented."""
    _setup_json_logging()

    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logger.info("OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return

    from opentelemetry import _logs, metrics
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import (
        ExplicitBucketHistogramAggregation,
        View,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "trialreads-api"),
            "service.version": APP_VERSION,
            "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
        }
    )

    # ── Traces ────────────────────────────────────────────────────────────
    # The no-arg exporter reads OTEL_EXPORTER_OTLP_ENDPOINT / _HEADERS from the
    # environment and appends the per-signal path (/v1/traces etc.) itself.
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # ── Metrics (set OTEL_METRICS_EXPORT=false for Jaeger, which is
    # traces-only and would 404 every export) ─────────────────────────────
    if os.getenv("OTEL_METRICS_EXPORT", "true").lower() != "false":
        # The AI endpoints routinely take 10-60s; the default histogram buckets
        # stop at 10s, which would clip their p95/p99 into +Inf. Extend the ladder.
        duration_view = View(
            instrument_name="http.server.request.duration",
            aggregation=ExplicitBucketHistogramAggregation(
                (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
                 1, 2.5, 5, 10, 20, 30, 60, 120)
            ),
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
            views=[duration_view],
        )
        metrics.set_meter_provider(meter_provider)

    # ── Logs (OTLP → Grafana Cloud lands them in Loki; no sidecar needed) ──
    # Jaeger accepts only traces, so set OTEL_LOGS_EXPORT=false alongside the
    # local Jaeger endpoint to avoid a 404 on every log batch.
    if os.getenv("OTEL_LOGS_EXPORT", "true").lower() != "false":
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter())
        )
        _logs.set_logger_provider(logger_provider)
        otel_log_handler = LoggingHandler(
            level=logging.INFO, logger_provider=logger_provider
        )
        # Never export the SDK's own logs: an export failure logs an ERROR,
        # which this handler would queue for export, which fails again — a
        # feedback loop. They still reach stdout via the root handler.
        otel_log_handler.addFilter(
            lambda record: not record.name.startswith("opentelemetry")
        )
        logging.getLogger().addHandler(otel_log_handler)

    # ── Auto-instrumentation ─────────────────────────────────────────────
    # FastAPI: a server span per request + the RED histogram, labeled by ROUTE
    # TEMPLATE (http.route = "/shelves/{shelf_id}"), method, and status code.
    # Route templates are a small fixed set, so metric cardinality stays tiny.
    # Raw paths or user ids as metric labels would create one time series per
    # distinct value — that unbounded growth is exactly how metrics bills and
    # query latency blow up. user_id therefore exists ONLY as a span attribute
    # (set in auth.py), never as a metric label.
    FastAPIInstrumentor.instrument_app(app, server_request_hook=_server_request_hook)
    # SQLAlchemy: global patch — every engine created AFTER this call is traced
    # (app.db's pooled engine and the per-request RLS engines in library_query).
    SQLAlchemyInstrumentor().instrument()
    # httpx: covers the OpenAI SDK's transport and our Google Books calls.
    HTTPXClientInstrumentor().instrument()

    global OTEL_ACTIVE
    OTEL_ACTIVE = True
    logger.info(
        "OpenTelemetry enabled: service=%s version=%s environment=%s endpoint=%s",
        resource.attributes.get("service.name"),
        APP_VERSION,
        resource.attributes.get("deployment.environment"),
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
