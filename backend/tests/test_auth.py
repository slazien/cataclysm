"""Tests for the JWT authentication dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from backend.api.config import Settings
from backend.api.dependencies import AuthenticatedUser, get_current_user

_SECRET = "test-nextauth-secret-key-for-unit-tests"


def _make_token(
    sub: str = "user-123",
    email: str = "driver@example.com",
    name: str = "Test Driver",
    picture: str | None = "https://example.com/avatar.jpg",
    secret: str = _SECRET,
    exp_hours: int = 24,
) -> str:
    """Create a signed JWT matching NextAuth.js format."""
    payload: dict[str, object] = {
        "sub": sub,
        "email": email,
        "name": name,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=exp_hours),
    }
    if picture:
        payload["picture"] = picture
    result: str = jwt.encode(payload, secret, algorithm="HS256")  # type: ignore[assignment]
    return result


def _settings(secret: str = _SECRET) -> Settings:
    """Build a Settings instance with the given secret."""
    return Settings(nextauth_secret=secret, anthropic_api_key="fake")


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_valid_bearer_token(self) -> None:
        token = _make_token()
        user = get_current_user(
            authorization=f"Bearer {token}",
            session_token=None,
            secure_session_token=None,
            settings=_settings(),
        )
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "user-123"
        assert user.email == "driver@example.com"
        assert user.name == "Test Driver"
        assert user.picture == "https://example.com/avatar.jpg"

    def test_valid_session_cookie(self) -> None:
        token = _make_token()
        user = get_current_user(
            authorization=None,
            session_token=token,
            secure_session_token=None,
            settings=_settings(),
        )
        assert user.user_id == "user-123"

    def test_valid_secure_cookie(self) -> None:
        token = _make_token()
        user = get_current_user(
            authorization=None,
            session_token=None,
            secure_session_token=token,
            settings=_settings(),
        )
        assert user.user_id == "user-123"

    def test_secure_cookie_takes_priority_over_session_cookie(self) -> None:
        token_secure = _make_token(sub="secure-user")
        token_session = _make_token(sub="session-user")
        user = get_current_user(
            authorization=None,
            session_token=token_session,
            secure_session_token=token_secure,
            settings=_settings(),
        )
        assert user.user_id == "secure-user"

    def test_bearer_takes_priority_over_cookies(self) -> None:
        token_bearer = _make_token(sub="bearer-user")
        token_cookie = _make_token(sub="cookie-user")
        user = get_current_user(
            authorization=f"Bearer {token_bearer}",
            session_token=token_cookie,
            secure_session_token=None,
            settings=_settings(),
        )
        assert user.user_id == "bearer-user"

    def test_missing_token_returns_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=None,
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in str(exc_info.value.detail)

    def test_invalid_jwt_returns_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization="Bearer not-a-real-jwt",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401
        assert "Invalid token" in str(exc_info.value.detail)

    def test_wrong_secret_returns_401(self) -> None:
        token = _make_token(secret="wrong-secret")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Bearer {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401

    def test_expired_token_returns_401(self) -> None:
        token = _make_token(exp_hours=-1)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Bearer {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401

    def test_missing_sub_claim_returns_401(self) -> None:
        payload = {
            "email": "driver@example.com",
            "name": "Test",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(payload, _SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Bearer {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401
        assert "Invalid token claims" in str(exc_info.value.detail)

    def test_missing_email_claim_returns_401(self) -> None:
        payload = {
            "sub": "user-123",
            "name": "Test",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(payload, _SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Bearer {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401

    def test_no_secret_configured_returns_503(self) -> None:
        token = _make_token()
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Bearer {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(secret=""),
            )
        assert exc_info.value.status_code == 503
        assert "Auth not configured" in str(exc_info.value.detail)

    def test_no_picture_returns_none(self) -> None:
        token = _make_token(picture=None)
        user = get_current_user(
            authorization=f"Bearer {token}",
            session_token=None,
            secure_session_token=None,
            settings=_settings(),
        )
        assert user.picture is None

    def test_authorization_header_without_bearer_prefix(self) -> None:
        """Non-Bearer auth header should be ignored, fall through to cookies."""
        token = _make_token()
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=f"Basic {token}",
                session_token=None,
                secure_session_token=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401
