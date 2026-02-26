"""Tests for the NHTSA UTQG API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cataclysm.utqg_client import lookup_treadwear

_FAKE_REQUEST = httpx.Request("GET", "https://data.transportation.gov/resource/rfqx-2vcg.json")


def _make_response(status_code: int, json_data: object = None) -> httpx.Response:
    """Build an httpx.Response with a request attached so raise_for_status works."""
    resp = httpx.Response(status_code=status_code, json=json_data, request=_FAKE_REQUEST)
    return resp


def _mock_client(
    response: httpx.Response | None = None,
    *,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """Build a mock AsyncClient context manager."""
    client = AsyncMock()
    if side_effect is not None:
        client.get = AsyncMock(side_effect=side_effect)
    else:
        client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_found_result_returns_treadwear() -> None:
    """When the API returns a matching record, return the treadwear as int."""
    resp = _make_response(
        200,
        [{"brandname": "BRIDGESTONE", "t_unifiedtm": "RE-71RS", "t_trdwr": "200"}],
    )
    mock = _mock_client(resp)

    with patch("cataclysm.utqg_client.httpx.AsyncClient", return_value=mock):
        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result == 200
    mock.get.assert_called_once()


@pytest.mark.asyncio
async def test_empty_results_returns_none() -> None:
    """When the API returns no records, return None."""
    resp = _make_response(200, [])
    mock = _mock_client(resp)

    with patch("cataclysm.utqg_client.httpx.AsyncClient", return_value=mock):
        result = await lookup_treadwear("Unknown", "TireXYZ")

    assert result is None


@pytest.mark.asyncio
async def test_api_error_returns_none() -> None:
    """When the API returns a 500 error, return None gracefully."""
    resp = _make_response(500)
    mock = _mock_client(resp)

    with patch("cataclysm.utqg_client.httpx.AsyncClient", return_value=mock):
        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result is None


@pytest.mark.asyncio
async def test_missing_treadwear_field_returns_none() -> None:
    """When the API record has no treadwear field, return None."""
    resp = _make_response(200, [{"brandname": "BRIDGESTONE", "t_unifiedtm": "RE-71RS"}])
    mock = _mock_client(resp)

    with patch("cataclysm.utqg_client.httpx.AsyncClient", return_value=mock):
        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result is None


@pytest.mark.asyncio
async def test_network_error_returns_none() -> None:
    """When a network error occurs, return None gracefully."""
    mock = _mock_client(side_effect=httpx.ConnectError("Connection refused"))

    with patch("cataclysm.utqg_client.httpx.AsyncClient", return_value=mock):
        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result is None
