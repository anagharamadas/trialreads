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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
