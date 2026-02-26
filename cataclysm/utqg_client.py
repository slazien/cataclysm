"""Async client for the NHTSA UTQG (Uniform Tire Quality Grading) API.

Queries the Socrata SODA API at ``data.transportation.gov`` to look up
treadwear ratings for a given tire brand and model.  Returns ``None``
when the tire cannot be found or the API is unreachable.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

UTQG_API_URL = "https://data.transportation.gov/resource/rfqx-2vcg.json"
REQUEST_TIMEOUT_S = 10.0


async def lookup_treadwear(brand: str, model: str) -> int | None:
    """Look up the UTQG treadwear rating for a tire.

    Sends a filtered query to the NHTSA Socrata API using ``brandname``
    and ``t_unifiedtm`` columns.

    Args:
        brand: Tire manufacturer name (e.g. ``"Bridgestone"``).
        model: Tire model identifier (e.g. ``"Potenza RE-71RS"``).

    Returns:
        The treadwear rating as an ``int``, or ``None`` if the tire was
        not found or the request failed.
    """
    where_clause = f"upper(brandname)=upper('{brand}') AND upper(t_unifiedtm)=upper('{model}')"
    params = {
        "$where": where_clause,
        "$limit": "1",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            response = await client.get(UTQG_API_URL, params=params)
            response.raise_for_status()

        data = response.json()
        if not data:
            logger.info("No UTQG results for brand=%r model=%r", brand, model)
            return None

        treadwear_raw = data[0].get("t_trdwr")
        if treadwear_raw is None:
            logger.warning("UTQG record missing treadwear field for %r %r", brand, model)
            return None

        return int(treadwear_raw)

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "UTQG API returned status %d for brand=%r model=%r",
            exc.response.status_code,
            brand,
            model,
        )
        return None
    except (httpx.RequestError, ValueError, KeyError, IndexError) as exc:
        logger.warning("UTQG lookup failed for brand=%r model=%r: %s", brand, model, exc)
        return None
