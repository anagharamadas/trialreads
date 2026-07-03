"""TrialReads backend — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="TrialReads API",
    description="Book summaries, personal library (text-to-SQL), and recommendations.",
    version="0.1.0",
)

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
    return {"status": "ok"}


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
