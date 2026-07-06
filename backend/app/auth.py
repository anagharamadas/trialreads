"""JWT authentication — verifies the Supabase access token and yields user_id.

The frontend sends Supabase's access token as `Authorization: Bearer <jwt>`.

This project's Supabase issues **ES256 (asymmetric)** tokens with a `kid`, verified
against the project's JWKS endpoint. We fetch + cache those public keys and verify
by key id. An HS256 path (legacy shared secret) is kept as a fallback so tokens
signed with SUPABASE_JWT_SECRET also validate — harmless since that secret is
backend-only.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from opentelemetry import trace

from .config import get_settings

_settings = get_settings()
_bearer = HTTPBearer(auto_error=False)

_EXPECTED_AUDIENCE = "authenticated"
_ASYMMETRIC_ALGS = ["ES256", "RS256"]

# JWKS endpoint for the project; keys are cached (refreshed periodically).
_JWKS_URL = f"{_settings.supabase_url}/auth/v1/.well-known/jwks.json"
_jwks_client = (
    PyJWKClient(_JWKS_URL, cache_keys=True) if _settings.supabase_url else None
)


def _credentials_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode(token: str) -> dict:
    """Verify the token. ES256/RS256 via JWKS; HS256 via the shared secret."""
    alg = jwt.get_unverified_header(token).get("alg", "")

    if alg == "HS256":
        return jwt.decode(
            token,
            _settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=_EXPECTED_AUDIENCE,
        )

    if _jwks_client is None:
        raise jwt.InvalidTokenError("JWKS not configured (SUPABASE_URL missing)")
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=_ASYMMETRIC_ALGS,
        audience=_EXPECTED_AUDIENCE,
    )


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency: return the authenticated user's UUID, or 401."""
    if creds is None or not creds.credentials:
        raise _credentials_error("Missing bearer token")

    try:
        payload = _decode(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _credentials_error("Token expired")
    except jwt.InvalidTokenError as exc:
        raise _credentials_error(f"Invalid token: {exc}")
    except Exception as exc:  # JWKS fetch / key errors
        raise _credentials_error(f"Token verification failed: {exc}")

    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_error("Token missing subject (sub)")

    # VERIFIED user_id onto the request span — a span attribute only (low
    # volume, high cardinality is fine on traces). Never a metric label.
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("app.user_id", user_id)
    return user_id
