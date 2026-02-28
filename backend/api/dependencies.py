"""FastAPI dependency injection functions."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Cookie, Depends, Header, HTTPException, WebSocket
from joserfc import jwe
from joserfc.errors import DecodeError
from joserfc.jwk import OctKey

from backend.api.config import Settings

logger = logging.getLogger(__name__)


_SECURE_COOKIE = "__Secure-authjs.session-token"
_SESSION_COOKIE = "authjs.session-token"


def _derive_encryption_key(secret: str, salt: str) -> bytes:
    """Derive a 64-byte key from a NextAuth secret using HKDF.

    Matches ``getDerivedEncryptionKey`` in Auth.js v5 (``@auth/core/jwt.ts``):
    ``A256CBC-HS512`` requires a 512-bit (64-byte) key.
    The HKDF salt and info both use the cookie name.
    """
    info = f"Auth.js Generated Encryption Key ({salt})".encode()
    hkdf = HKDF(
        algorithm=SHA256(),
        length=64,
        salt=salt.encode(),
        info=info,
    )
    return hkdf.derive(secret.encode())


def _decrypt_nextauth_token(token: str, secret: str, salt: str) -> dict[str, Any]:
    """Decrypt a NextAuth v5 JWE token and return its payload.

    Raises ``DecodeError`` if the token cannot be decrypted.
    Raises ``ValueError`` if the token is expired.
    """
    raw_key = _derive_encryption_key(secret, salt)
    key = OctKey.import_key(raw_key)
    result = jwe.decrypt_compact(token, key)
    plaintext = result.plaintext
    if plaintext is None:
        raise DecodeError("JWE decryption produced no plaintext")
    payload: dict[str, Any] = json.loads(plaintext)

    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        raise ValueError("Token has expired")

    return payload


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
    # QA bypass: skip all auth when DEV_AUTH_BYPASS=true
    if settings.dev_auth_bypass:
        return AuthenticatedUser(
            user_id="dev-user",
            email="dev@localhost",
            name="QA Test User",
        )

    if not settings.nextauth_secret:
        raise HTTPException(status_code=503, detail="Auth not configured")

    # Dev bypass: when using the default dev secret and no token is present,
    # return a dev user so local Docker works without Google OAuth.
    dev_secret = "dev-secret-do-not-use-in-production"
    is_dev = settings.nextauth_secret == dev_secret

    # Resolve token from header or cookies, tracking which cookie name (salt)
    token: str | None = None
    salt = _SECURE_COOKIE  # default salt for production
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        salt = _SECURE_COOKIE
    elif secure_session_token:
        token = secure_session_token
        salt = _SECURE_COOKIE
    elif session_token:
        token = session_token
        salt = _SESSION_COOKIE

    if not token:
        logger.warning(
            "Auth: no token found (header=%s, secure=%s, session=%s)",
            bool(authorization),
            bool(secure_session_token),
            bool(session_token),
        )
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = _decrypt_nextauth_token(token, settings.nextauth_secret, salt)
    except (DecodeError, ValueError, Exception) as exc:
        logger.warning("Auth: token decryption failed: %s: %s", type(exc).__name__, exc)
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

    # QA bypass: skip all auth when DEV_AUTH_BYPASS=true
    if settings.dev_auth_bypass:
        return AuthenticatedUser(
            user_id="dev-user",
            email="dev@localhost",
            name="QA Test User",
        )

    if not settings.nextauth_secret:
        return None

    dev_secret = "dev-secret-do-not-use-in-production"
    is_dev = settings.nextauth_secret == dev_secret

    cookies = websocket.cookies
    token: str | None = None
    salt = _SECURE_COOKIE
    if cookies.get(_SECURE_COOKIE):
        token = cookies[_SECURE_COOKIE]
        salt = _SECURE_COOKIE
    elif cookies.get(_SESSION_COOKIE):
        token = cookies[_SESSION_COOKIE]
        salt = _SESSION_COOKIE
    if not token:
        if is_dev:
            return AuthenticatedUser(
                user_id="dev-user",
                email="dev@localhost",
                name="Dev User",
            )
        return None

    try:
        payload = _decrypt_nextauth_token(token, settings.nextauth_secret, salt)
    except (DecodeError, ValueError, Exception):
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
