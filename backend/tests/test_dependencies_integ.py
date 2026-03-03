"""Integration tests for backend/api/dependencies.py.

Covers uncovered lines:
  - Line 56: DecodeError("JWE decryption produced no plaintext")
  - Lines 133-138: dev secret + no token → dev user fallback
  - Lines 145-150: dev secret + bad token → dev user fallback
  - Lines 176-231: authenticate_websocket function
  - Config lines 24-29: Settings._parse_cors_origins fallback paths
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from joserfc import jwe
from joserfc.errors import DecodeError
from joserfc.jwk import OctKey

from backend.api.config import Settings, _parse_cors_origins
from backend.api.dependencies import (
    _SECURE_COOKIE,
    _SESSION_COOKIE,
    AuthenticatedUser,
    _decrypt_nextauth_token,
    _derive_encryption_key,
    authenticate_websocket,
    get_current_user,
)

_DEV_SECRET = "dev-secret-do-not-use-in-production"
_PROD_SECRET = "prod-nextauth-secret-for-testing"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    sub: str = "user-xyz",
    email: str = "driver@example.com",
    name: str = "Test Driver",
    secret: str = _PROD_SECRET,
    salt: str = _SECURE_COOKIE,
    exp_hours: int = 24,
) -> str:
    """Encrypt a NextAuth.js-compatible JWE token."""
    payload: dict[str, object] = {
        "sub": sub,
        "email": email,
        "name": name,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(hours=exp_hours)).timestamp()),
    }
    raw_key = _derive_encryption_key(secret, salt)
    key = OctKey.import_key(raw_key)
    protected = {"alg": "dir", "enc": "A256CBC-HS512"}
    return jwe.encrypt_compact(protected, json.dumps(payload).encode(), key)


def _settings(**kwargs: object) -> Settings:
    """Build a Settings instance. Defaults to the prod test secret."""
    kwargs.setdefault("nextauth_secret", _PROD_SECRET)
    kwargs.setdefault("anthropic_api_key", "fake")
    return Settings(**kwargs)  # type: ignore[arg-type]


def _mock_websocket(cookies: dict[str, str], headers: dict[str, str] | None = None) -> MagicMock:
    """Build a minimal WebSocket mock with the given cookies."""
    ws = MagicMock()
    ws.cookies = cookies
    ws.headers = headers or {}
    return ws


# ===========================================================================
# _decrypt_nextauth_token — unit tests for uncovered branches
# ===========================================================================


class TestDecryptNextauthToken:
    """Unit tests for _decrypt_nextauth_token directly."""

    def test_invalid_token_raises_decode_error(self) -> None:
        """A completely invalid token string raises DecodeError."""
        with pytest.raises(DecodeError):
            _decrypt_nextauth_token("not.a.real.jwe.token", _PROD_SECRET, _SECURE_COOKIE)

    def test_expired_token_raises_value_error(self) -> None:
        """A validly encrypted but expired token raises ValueError."""
        token = _make_token(exp_hours=-1)
        with pytest.raises(ValueError, match="expired"):
            _decrypt_nextauth_token(token, _PROD_SECRET, _SECURE_COOKIE)

    def test_valid_token_returns_payload(self) -> None:
        """A valid, non-expired token returns the decrypted payload dict."""
        token = _make_token(sub="test-sub", email="x@x.com")
        payload = _decrypt_nextauth_token(token, _PROD_SECRET, _SECURE_COOKIE)
        assert payload["sub"] == "test-sub"
        assert payload["email"] == "x@x.com"

    def test_wrong_secret_raises_decode_error(self) -> None:
        """Token encrypted with a different secret raises DecodeError on decryption."""
        token = _make_token(secret="other-secret")
        with pytest.raises((DecodeError, Exception)):
            _decrypt_nextauth_token(token, _PROD_SECRET, _SECURE_COOKIE)

    def test_plaintext_none_raises_decode_error(self) -> None:
        """When joserfc returns None plaintext the function raises DecodeError (line 56)."""
        token = _make_token()
        # Patch jwe.decrypt_compact to return a result with plaintext=None
        mock_result = MagicMock()
        mock_result.plaintext = None
        with (
            patch("backend.api.dependencies.jwe.decrypt_compact", return_value=mock_result),
            pytest.raises(DecodeError, match="no plaintext"),
        ):
            _decrypt_nextauth_token(token, _PROD_SECRET, _SECURE_COOKIE)


# ===========================================================================
# get_current_user — dev-secret fallback branches (lines 133-138, 145-150)
# ===========================================================================


class TestGetCurrentUserDevSecretFallback:
    """Test dev secret fallback paths not covered by test_auth.py."""

    def test_dev_secret_no_token_returns_dev_user(self) -> None:
        """Dev secret + no token → returns Dev User (line 133-138)."""
        settings = _settings(nextauth_secret=_DEV_SECRET)
        user = get_current_user(
            authorization=None,
            session_token=None,
            secure_session_token=None,
            settings=settings,
        )
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "dev-user"
        assert user.email == "dev@localhost"
        assert user.name == "Dev User"

    def test_dev_secret_bad_token_returns_dev_user(self) -> None:
        """Dev secret + bad/corrupt token → returns Dev User (lines 145-150)."""
        settings = _settings(nextauth_secret=_DEV_SECRET)
        user = get_current_user(
            authorization="Bearer totally-invalid-token",
            session_token=None,
            secure_session_token=None,
            settings=settings,
        )
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "dev-user"
        assert user.name == "Dev User"

    def test_dev_secret_token_wrong_secret_returns_dev_user(self) -> None:
        """Token encrypted with prod secret but env uses dev secret → dev user fallback."""
        settings = _settings(nextauth_secret=_DEV_SECRET)
        token = _make_token(secret=_PROD_SECRET)
        user = get_current_user(
            authorization=f"Bearer {token}",
            session_token=None,
            secure_session_token=None,
            settings=settings,
        )
        assert user.user_id == "dev-user"

    def test_no_secret_configured_returns_503(self) -> None:
        """No nextauth_secret configured → 503 Service Unavailable."""
        from fastapi import HTTPException

        settings = _settings(nextauth_secret="")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=None,
                session_token=None,
                secure_session_token=None,
                settings=settings,
            )
        assert exc_info.value.status_code == 503

    def test_prod_secret_no_token_returns_401(self) -> None:
        """Prod secret + no token → 401 Unauthorized (no dev fallback)."""
        from fastapi import HTTPException

        settings = _settings(nextauth_secret=_PROD_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=None,
                session_token=None,
                secure_session_token=None,
                settings=settings,
            )
        assert exc_info.value.status_code == 401

    def test_prod_secret_bad_token_returns_401(self) -> None:
        """Prod secret + bad token → 401 Unauthorized (no dev fallback)."""
        from fastapi import HTTPException

        settings = _settings(nextauth_secret=_PROD_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization="Bearer garbage",
                session_token=None,
                secure_session_token=None,
                settings=settings,
            )
        assert exc_info.value.status_code == 401


# ===========================================================================
# authenticate_websocket — lines 176-231
# ===========================================================================


class TestAuthenticateWebsocket:
    """Tests for the authenticate_websocket async dependency (lines 176-231)."""

    @pytest.mark.asyncio
    async def test_dev_auth_bypass_returns_dev_user(self) -> None:
        """DEV_AUTH_BYPASS=True → QA dev user regardless of cookies (lines 179-184)."""
        ws = _mock_websocket({})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(dev_auth_bypass=True)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "dev-user"
        assert result.name == "QA Test User"

    @pytest.mark.asyncio
    async def test_no_secret_returns_none(self) -> None:
        """No nextauth_secret configured → returns None (line 187)."""
        ws = _mock_websocket({})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret="")
            result = await authenticate_websocket(ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_dev_secret_no_cookies_returns_dev_user(self) -> None:
        """Dev secret + no cookies → Dev User fallback (lines 202-207)."""
        ws = _mock_websocket({})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_DEV_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "dev-user"
        assert result.name == "Dev User"

    @pytest.mark.asyncio
    async def test_dev_secret_bad_cookie_returns_dev_user(self) -> None:
        """Dev secret + corrupt cookie → Dev User fallback (lines 213-218)."""
        ws = _mock_websocket({_SESSION_COOKIE: "not-a-valid-jwe"})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_DEV_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "dev-user"

    @pytest.mark.asyncio
    async def test_prod_secret_no_cookies_returns_none(self) -> None:
        """Prod secret + no cookies → None (line 208)."""
        ws = _mock_websocket({})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_prod_secret_bad_cookie_returns_none(self) -> None:
        """Prod secret + bad cookie → None (line 219)."""
        ws = _mock_websocket({_SESSION_COOKIE: "garbage-token"})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_secure_cookie_returns_user(self) -> None:
        """Valid __Secure-authjs.session-token cookie → authenticated user (lines 195-197)."""
        token = _make_token(sub="ws-user", email="ws@example.com", salt=_SECURE_COOKIE)
        ws = _mock_websocket({_SECURE_COOKIE: token})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "ws-user"
        assert result.email == "ws@example.com"

    @pytest.mark.asyncio
    async def test_valid_session_cookie_returns_user(self) -> None:
        """Valid authjs.session-token cookie → authenticated user (lines 198-200)."""
        token = _make_token(sub="ws-session-user", email="sess@example.com", salt=_SESSION_COOKIE)
        ws = _mock_websocket({_SESSION_COOKIE: token})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "ws-session-user"
        assert result.email == "sess@example.com"

    @pytest.mark.asyncio
    async def test_secure_cookie_takes_priority_over_session_cookie(self) -> None:
        """When both cookies present, __Secure- cookie wins."""
        secure_token = _make_token(sub="secure-ws", salt=_SECURE_COOKIE)
        session_token = _make_token(sub="session-ws", salt=_SESSION_COOKIE)
        ws = _mock_websocket(
            {
                _SECURE_COOKIE: secure_token,
                _SESSION_COOKIE: session_token,
            }
        )
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.user_id == "secure-ws"

    @pytest.mark.asyncio
    async def test_missing_sub_claim_returns_none(self) -> None:
        """Token without 'sub' claim → returns None (line 224)."""
        payload = {
            "email": "nosub@example.com",
            "name": "No Sub",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }
        raw_key = _derive_encryption_key(_PROD_SECRET, _SECURE_COOKIE)
        key = OctKey.import_key(raw_key)
        protected = {"alg": "dir", "enc": "A256CBC-HS512"}
        token = jwe.encrypt_compact(protected, json.dumps(payload).encode(), key)
        ws = _mock_websocket({_SECURE_COOKIE: token})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_email_claim_returns_none(self) -> None:
        """Token without 'email' claim → returns None (line 224)."""
        payload = {
            "sub": "user-noemail",
            "name": "No Email",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }
        raw_key = _derive_encryption_key(_PROD_SECRET, _SECURE_COOKIE)
        key = OctKey.import_key(raw_key)
        protected = {"alg": "dir", "enc": "A256CBC-HS512"}
        token = jwe.encrypt_compact(protected, json.dumps(payload).encode(), key)
        ws = _mock_websocket({_SECURE_COOKIE: token})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_picture_field_propagated(self) -> None:
        """Optional 'picture' field is passed through to AuthenticatedUser."""
        payload = {
            "sub": "pic-user",
            "email": "pic@example.com",
            "name": "Pic User",
            "picture": "https://example.com/photo.jpg",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }
        raw_key = _derive_encryption_key(_PROD_SECRET, _SECURE_COOKIE)
        key = OctKey.import_key(raw_key)
        protected = {"alg": "dir", "enc": "A256CBC-HS512"}
        token = jwe.encrypt_compact(protected, json.dumps(payload).encode(), key)
        ws = _mock_websocket({_SECURE_COOKIE: token})
        with patch("backend.api.dependencies.get_settings") as mock_get:
            mock_get.return_value = _settings(nextauth_secret=_PROD_SECRET)
            result = await authenticate_websocket(ws)
        assert result is not None
        assert result.picture == "https://example.com/photo.jpg"


# ===========================================================================
# config.py — _parse_cors_origins (lines 24-29)
# ===========================================================================


class TestParseCorsOrigins:
    """Tests for the _parse_cors_origins helper covering all three parse paths."""

    def test_valid_json_array(self) -> None:
        """Valid JSON array string is parsed correctly."""
        result = _parse_cors_origins('["https://a.com","https://b.com"]')
        assert result == ["https://a.com", "https://b.com"]

    def test_bracketed_non_json_railway_format(self) -> None:
        """Railway-stripped format [https://a.com,https://b.com] is handled (lines 27-29)."""
        result = _parse_cors_origins("[https://a.com,https://b.com]")
        assert result == ["https://a.com", "https://b.com"]

    def test_comma_separated_no_brackets(self) -> None:
        """Bare comma-separated URLs without brackets (lines 27-29)."""
        result = _parse_cors_origins("https://a.com,https://b.com")
        assert result == ["https://a.com", "https://b.com"]

    def test_single_url_json(self) -> None:
        """Single URL as a JSON array."""
        result = _parse_cors_origins('["https://only.com"]')
        assert result == ["https://only.com"]

    def test_single_url_bare(self) -> None:
        """Single bare URL with no brackets."""
        result = _parse_cors_origins("https://only.com")
        assert result == ["https://only.com"]

    def test_quoted_entries_stripped(self) -> None:
        """Entries wrapped in extra quotes are stripped."""
        result = _parse_cors_origins('[  "https://a.com" ,  "https://b.com"  ]')
        assert result == ["https://a.com", "https://b.com"]

    def test_settings_cors_origins_property_returns_list(self) -> None:
        """Settings.cors_origins property delegates to _parse_cors_origins."""
        s = Settings(cors_origins_raw='["http://localhost:3000"]')
        assert s.cors_origins == ["http://localhost:3000"]

    def test_settings_cors_origins_property_railway_format(self) -> None:
        """Settings.cors_origins handles Railway's non-JSON format."""
        s = Settings(cors_origins_raw="[http://localhost:3000]")
        assert s.cors_origins == ["http://localhost:3000"]
