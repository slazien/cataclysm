"""OSM Overpass API client for raceway centerline import."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass
class OverpassResult:
    osm_id: int
    name: str
    lats: list[float]
    lons: list[float]
    length_m: float


@dataclass
class Centerline:
    lats: np.ndarray
    lons: np.ndarray
    length_m: float


async def _fetch_overpass(query: str) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_OVERPASS_URL, data={"data": query})
        resp.raise_for_status()
        return resp.json()


def _fetch_overpass_sync(query: str) -> Any:
    """Synchronous version for use from pipeline thread."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_OVERPASS_URL, data={"data": query})
        resp.raise_for_status()
        return resp.json()


async def query_overpass_raceway(
    lat: float, lon: float, radius_m: int = 5000
) -> list[OverpassResult]:
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"="raceway"](around:{radius_m},{lat},{lon});
      way["leisure"="sports_centre"]["sport"~"motor|karting"](around:{radius_m},{lat},{lon});
    );
    out geom;
    """
    data = await _fetch_overpass(query)
    results = []
    for el in data.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        geom = el["geometry"]
        name = el.get("tags", {}).get("name", f"OSM Way {el['id']}")
        cl = extract_centerline(geom)
        results.append(
            OverpassResult(
                osm_id=el["id"],
                name=name,
                lats=cl.lats.tolist(),
                lons=cl.lons.tolist(),
                length_m=cl.length_m,
            )
        )
    return results


def extract_centerline(geom: list[dict[str, float]]) -> Centerline:
    lats = np.array([p["lat"] for p in geom])
    lons = np.array([p["lon"] for p in geom])
    dlat = np.diff(lats) * 111320.0
    dlon = np.diff(lons) * 111320.0 * np.cos(np.radians(np.mean(lats)))
    seg_lens = np.sqrt(dlat**2 + dlon**2)
    return Centerline(lats=lats, lons=lons, length_m=float(np.sum(seg_lens)))


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def osm_to_track_seed(result: OverpassResult) -> dict[str, Any]:
    return {
        "slug": _slugify(result.name),
        "name": result.name,
        "source": "osm",
        "center_lat": float(np.mean(result.lats)),
        "center_lon": float(np.mean(result.lons)),
        "length_m": result.length_m,
    }


def query_overpass_raceway_sync(
    lat: float, lon: float, radius_m: int = 5000
) -> list[OverpassResult]:
    """Synchronous version of query_overpass_raceway for pipeline thread."""
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"="raceway"](around:{radius_m},{lat},{lon});
    );
    out geom;
    """
    try:
        data = _fetch_overpass_sync(query)
    except (httpx.HTTPError, httpx.TimeoutException):
        logger.warning("OSM Overpass query failed for %.4f,%.4f", lat, lon, exc_info=True)
        return []

    results = []
    for el in data.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        geom = el["geometry"]
        name = el.get("tags", {}).get("name", f"OSM Way {el['id']}")
        cl = extract_centerline(geom)
        # Filter: only real raceways (>500m length, reasonable geometry)
        if cl.length_m < 500:
            continue
        results.append(
            OverpassResult(
                osm_id=el["id"],
                name=name,
                lats=cl.lats.tolist(),
                lons=cl.lons.tolist(),
                length_m=cl.length_m,
            )
        )
    return results
