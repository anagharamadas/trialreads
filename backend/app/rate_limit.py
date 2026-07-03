"""Per-user daily rate limiting for the AI endpoints (Milestone 6).

The AI endpoints (/summarise, /recommend, /library/query) are the only paid
resource. This caps how many a single user can make per day, backed by the
`ai_usage` Postgres table so the count survives Render cold starts and is shared
across instances.

Usage: AI endpoints depend on `rate_limited_user` instead of `get_current_user_id`
— it authenticates AND enforces the cap, returning the user_id.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import text

from .auth import get_current_user_id
from .config import get_settings
from .db import engine

settings = get_settings()


def rate_limited_user(user_id: str = Depends(get_current_user_id)) -> str:
    """Increment today's counter for this user; 429 if over the daily cap."""
    with engine.begin() as conn:
        count = conn.execute(
            text(
                "INSERT INTO public.ai_usage (user_id, day, count) "
                "VALUES (:u, current_date, 1) "
                "ON CONFLICT (user_id, day) "
                "DO UPDATE SET count = ai_usage.count + 1 "
                "RETURNING count"
            ),
            {"u": user_id},
        ).scalar_one()

    if count > settings.daily_ai_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily AI limit reached ({settings.daily_ai_limit} requests). "
                "Try again tomorrow."
            ),
        )
    return user_id
