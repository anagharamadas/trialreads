"""Eval-harness configuration — read from backend/.env + process env.

Reuses the app's own Settings for OPENAI_API_KEY / DATABASE_URL so the eval hits
exactly the same OpenAI account and Supabase Postgres the API does. The only
eval-specific value is EVAL_USER_ID: the auth.users UUID whose library holds the
fixture (see seed_fixture.py). Keep it a throwaway account — the seed WIPES that
user's library rows.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings

EVALS_DIR = Path(__file__).resolve().parent
ENV_FILE = EVALS_DIR.parent / ".env"

# Mirror telemetry.py / the seed script: load backend/.env into os.environ so
# EVAL_* vars can live alongside the app's settings in the same file.
load_dotenv(ENV_FILE)

_settings = get_settings()


def eval_user_id() -> str:
    return os.getenv("EVAL_USER_ID", "").strip()


def openai_api_key() -> str:
    # Settings first (its own .env load), env var as override/fallback.
    return _settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")


def database_url() -> str:
    return _settings.database_url or os.getenv("DATABASE_URL", "")


# gpt-4o-mini matches the model the features themselves use; temp 0 for a stable,
# reproducible judge. Overridable so you can trial a stronger judge model.
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gpt-4o-mini")

# A run "passes" (exit code 0) only if the pass rate clears this bar — makes the
# harness usable as a CI gate later.
PASS_THRESHOLD = float(os.getenv("EVAL_PASS_THRESHOLD", "0.8"))

DATASETS_DIR = EVALS_DIR / "datasets"
FIXTURES_DIR = EVALS_DIR / "fixtures"
REPORTS_DIR = EVALS_DIR / "reports"
