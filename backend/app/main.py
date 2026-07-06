"""TrialReads backend — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import telemetry
from .config import get_settings
from .telemetry import APP_VERSION, seconds_since_boot, setup_telemetry

settings = get_settings()

# Error monitoring (no-op unless SENTRY_DSN is set).
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment="development" if settings.debug else "production",
    )

app = FastAPI(
    title="TrialReads API",
    description="Book summaries, personal library (text-to-SQL), and recommendations.",
    version="0.1.0",
)

# Telemetry must be configured BEFORE the routers below are imported: importing
# them imports app.db, and the SQLAlchemy engine must be created after the
# instrumentation patch to be traced. No-op unless OTEL_EXPORTER_OTLP_ENDPOINT
# is set (structured JSON logging is configured either way).
setup_telemetry(app)

# Explicit allowlist (e.g. the deployed Vercel domain) from settings. In dev we
# ALSO allow any localhost port via regex — Next.js auto-bumps 3000 -> 3001/3002…
# when a port is taken, and a hardcoded single port silently breaks every API
# call with a CORS preflight failure. In production set CORS_ALLOW_LOCALHOST=false
# so only the Vercel domain is permitted.
_cors_kwargs: dict = dict(
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.cors_allow_localhost:
    _cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.get("/health", tags=["meta"])
def health():
    """Cheap liveness probe: no auth, no DB, no external calls. Used by Render's
    health check and Grafana Synthetic Monitoring. uptime_seconds makes Render
    free-tier spin-downs visible (a small value right after traffic = cold start).
    """
    import os

    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": seconds_since_boot(),
        # True only when the OTLP env vars were present at startup — the
        # definitive "is this process exporting to Grafana?" check.
        "otel_enabled": telemetry.OTEL_ACTIVE,
        # TEMPORARY (Phase 3 M2 debugging): which OTEL_* variable NAMES the
        # process sees, with value lengths — never values. Lets us distinguish
        # "var not set at all" from "name typo" without Render log access.
        # Remove once Grafana ingestion is confirmed.
        "otel_env_seen": {
            k: len(v) for k, v in os.environ.items() if k.upper().startswith("OTEL")
        },
    }


# Routers are added stage by stage (Stage B: library, Stage C/D: ai).
try:
    from .routers import library as _library

    app.include_router(_library.router)
except ImportError:
    pass

try:
    from .routers import ai as _ai

    app.include_router(_ai.router)
except ImportError:
    pass

try:
    from .routers import covers as _covers

    app.include_router(_covers.router)
except ImportError:
    pass

try:
    from .routers import shelves as _shelves

    app.include_router(_shelves.router)
except ImportError:
    pass
