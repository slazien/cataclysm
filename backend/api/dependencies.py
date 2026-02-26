"""FastAPI dependency injection functions."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, WebSocket
from jose import JWTError, jwt

from backend.api.config import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton application settings."""
    return Settings()


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Represents a verified user extracted from a NextAuth.js JWT."""

    user_id: str
    email: str
    name: str
    picture: str | None = None


def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
    session_token: str | None = Cookie(None, alias="authjs.session-token"),
    secure_session_token: str | None = Cookie(None, alias="__Secure-authjs.session-token"),
) -> AuthenticatedUser:
    """Extract and validate user from NextAuth.js JWT.

    Checks (in order):
    1. ``Authorization: Bearer <token>`` header
    2. ``authjs.session-token`` cookie (development)
    3. ``__Secure-authjs.session-token`` cookie (production HTTPS)

    Returns 401 if no valid token, 503 if ``nextauth_secret`` is not configured.
    """
    if not settings.nextauth_secret:
        raise HTTPException(status_code=503, detail="Auth not configured")

    # Dev bypass: when using the default dev secret and no token is present,
    # return a dev user so local Docker works without Google OAuth.
    dev_secret = "dev-secret-do-not-use-in-production"
    is_dev = settings.nextauth_secret == dev_secret

    # Resolve token from header or cookies
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif secure_session_token:
        token = secure_session_token
    elif session_token:
        token = session_token

    if not token:
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        raise HTTPException(status_code=401, detail="Invalid token") from None

    # NextAuth.js JWT stores user info in ``sub``, ``email``, ``name``, ``picture``
    user_id = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name", "")

    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    return AuthenticatedUser(
        user_id=user_id,
        email=email,
        name=name,
        picture=payload.get("picture"),
    )


async def authenticate_websocket(websocket: WebSocket) -> AuthenticatedUser | None:
    """Validate a WebSocket connection using cookies.

    Returns the authenticated user or ``None`` if authentication fails.
    Unlike the HTTP dependency, this cannot use ``Header``/``Cookie``
    extractors — we read directly from the WebSocket scope.
    """
    settings = get_settings()
    if not settings.nextauth_secret:
        return None

    dev_secret = "dev-secret-do-not-use-in-production"
    is_dev = settings.nextauth_secret == dev_secret

    cookies = websocket.cookies
    token: str | None = cookies.get("__Secure-authjs.session-token") or cookies.get(
        "authjs.session-token"
    )
    if not token:
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        return None

    try:
        payload = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        return None

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        return None

    return AuthenticatedUser(
        user_id=user_id,
        email=email,
        name=payload.get("name", ""),
        picture=payload.get("picture"),
    )
