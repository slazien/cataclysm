"""Tests for rate limiting middleware."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limiter_installed(client: AsyncClient) -> None:
    """Verify the slowapi limiter is wired into the FastAPI app."""
    from slowapi.errors import RateLimitExceeded

    from backend.api.main import app

    # Verify the exception handler is registered for RateLimitExceeded
    handlers = app.exception_handlers
    assert RateLimitExceeded in handlers


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited(client: AsyncClient) -> None:
    """Health checks should not be affected by rate limiting."""
    for _ in range(5):
        response = await client.get("/health")
        assert response.status_code == 200
