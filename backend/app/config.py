"""Typed application settings, loaded from backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # OpenAI
    openai_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Postgres (Supabase) connection string
    database_url: str = ""

    # Google Books (M3)
    google_books_api_key: str = ""

    # Rate limiting (M6): max AI calls (summarise + recommend + query) per user/day
    daily_ai_limit: int = 50

    # Error monitoring (M6): Sentry DSN (empty = disabled)
    sentry_dsn: str = ""

    # Server
    debug: bool = False
    port: int = 8000
    host: str = "0.0.0.0"

    # CORS — comma-or-JSON list of allowed origins (e.g. the Vercel domain in prod)
    cors_origins: str = "http://localhost:3000"
    # Allow any localhost port (dev convenience). Set false in production so only
    # the explicit cors_origins (your Vercel domain) are permitted.
    cors_allow_localhost: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        def clean(o: str) -> str:
            # Browsers send the Origin with NO trailing slash and no path, so a
            # value like "https://app.vercel.app/" must be normalized or it never
            # matches. Also tolerate stray quotes/whitespace.
            return o.strip().strip('"').strip("'").rstrip("/")

        raw = self.cors_origins.strip()
        if raw.startswith("["):
            # tolerate JSON-ish '["http://localhost:3000"]'
            import json

            try:
                return [clean(str(o)) for o in json.loads(raw)]
            except Exception:
                pass
        return [clean(o) for o in raw.split(",") if clean(o)]


@lru_cache
def get_settings() -> Settings:
    return Settings()
