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

    # Server
    debug: bool = False
    port: int = 8000
    host: str = "0.0.0.0"

    # CORS — comma-or-JSON list of allowed origins
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            # tolerate JSON-ish '["http://localhost:3000"]'
            import json

            try:
                return [str(o) for o in json.loads(raw)]
            except Exception:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
