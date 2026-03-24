"""CRUD operations for CornerCapabilityFactor -- Bayesian per-corner learning."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CornerCapabilityFactor

logger = logging.getLogger(__name__)


async def get_corner_capabilities(
    db: AsyncSession,
    track_slug: str,
    user_id: str,
) -> dict[int, tuple[float, float, int]]:
    """Load all C-factors for a track+user.

    Returns ``{corner_number: (mu_posterior, sigma_posterior, n_observations)}``.
    """
    stmt = select(CornerCapabilityFactor).where(
        CornerCapabilityFactor.track_slug == track_slug,
        CornerCapabilityFactor.user_id == user_id,
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        row.corner_number: (row.mu_posterior, row.sigma_posterior, row.n_observations)
        for row in rows
    }


async def upsert_corner_capability(
    db: AsyncSession,
    track_slug: str,
    corner_number: int,
    user_id: str,
    mu_posterior: float,
    sigma_posterior: float,
    n_observations: int,
) -> None:
    """Insert or update a corner capability factor."""
    stmt = select(CornerCapabilityFactor).where(
        CornerCapabilityFactor.track_slug == track_slug,
        CornerCapabilityFactor.corner_number == corner_number,
        CornerCapabilityFactor.user_id == user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.mu_posterior = mu_posterior
        existing.sigma_posterior = sigma_posterior
        existing.n_observations = n_observations
    else:
        db.add(
            CornerCapabilityFactor(
                track_slug=track_slug,
                corner_number=corner_number,
                user_id=user_id,
                mu_posterior=mu_posterior,
                sigma_posterior=sigma_posterior,
                n_observations=n_observations,
            )
        )
    await db.flush()
