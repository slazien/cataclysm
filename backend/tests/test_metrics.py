from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_request" in resp.text or "HELP" in resp.text
