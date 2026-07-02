"""JWT authentication — verifies the Supabase access token and yields user_id.

The frontend sends Supabase's access token as `Authorization: Bearer <jwt>`.
This dependency verifies the signature + claims and returns the `sub` (the
Supabase auth user id).

Verification method: HS256 against SUPABASE_JWT_SECRET (the classic Supabase
approach). Structured so it can be swapped to asymmetric/JWKS verification if the
project uses the new signing keys — we confirm against a real token in M3.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

_settings = get_settings()
_bearer = HTTPBearer(auto_error=False)

# Supabase access tokens carry aud="authenticated".
_EXPECTED_AUDIENCE = "authenticated"


def _credentials_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency: return the authenticated user's UUID, or 401."""
    if creds is None or not creds.credentials:
        raise _credentials_error("Missing bearer token")

    token = creds.credentials
    try:
        payload = jwt.decode(
            token,
            _settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=_EXPECTED_AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        raise _credentials_error("Token expired")
    except jwt.InvalidTokenError as exc:
        raise _credentials_error(f"Invalid token: {exc}")

    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_error("Token missing subject (sub)")
    return user_id
