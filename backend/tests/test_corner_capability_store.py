"""Tests for corner_capability_store: DB CRUD for Bayesian C-factors."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.corner_capability_store import (
    get_corner_capabilities,
    upsert_corner_capability,
)
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestCornerCapabilityStore:
    @pytest.mark.asyncio
    async def test_empty_returns_empty_dict(self, db_session: AsyncSession) -> None:
        result = await get_corner_capabilities(db_session, "barber", "user-1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_upsert_and_read_round_trip(self, db_session: AsyncSession) -> None:
        await upsert_corner_capability(
            db_session,
            "barber",
            3,
            "user-1",
            mu_posterior=1.05,
            sigma_posterior=0.08,
            n_observations=2,
        )
        await db_session.commit()

        caps = await get_corner_capabilities(db_session, "barber", "user-1")
        assert 3 in caps
        mu, sigma, n = caps[3]
        assert abs(mu - 1.05) < 1e-6
        assert abs(sigma - 0.08) < 1e-6
        assert n == 2

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db_session: AsyncSession) -> None:
        await upsert_corner_capability(
            db_session,
            "barber",
            5,
            "user-1",
            mu_posterior=0.95,
            sigma_posterior=0.10,
            n_observations=1,
        )
        await db_session.commit()

        # Update with new values
        await upsert_corner_capability(
            db_session,
            "barber",
            5,
            "user-1",
            mu_posterior=0.97,
            sigma_posterior=0.07,
            n_observations=3,
        )
        await db_session.commit()

        caps = await get_corner_capabilities(db_session, "barber", "user-1")
        assert len(caps) == 1
        mu, sigma, n = caps[5]
        assert abs(mu - 0.97) < 1e-6
        assert n == 3

    @pytest.mark.asyncio
    async def test_isolation_by_user(self, db_session: AsyncSession) -> None:
        await upsert_corner_capability(
            db_session,
            "barber",
            1,
            "alice",
            mu_posterior=1.10,
            sigma_posterior=0.06,
            n_observations=5,
        )
        await upsert_corner_capability(
            db_session,
            "barber",
            1,
            "bob",
            mu_posterior=0.90,
            sigma_posterior=0.09,
            n_observations=3,
        )
        await db_session.commit()

        alice_caps = await get_corner_capabilities(db_session, "barber", "alice")
        bob_caps = await get_corner_capabilities(db_session, "barber", "bob")
        assert alice_caps[1][0] > bob_caps[1][0]

    @pytest.mark.asyncio
    async def test_isolation_by_track(self, db_session: AsyncSession) -> None:
        await upsert_corner_capability(
            db_session,
            "barber",
            1,
            "user-1",
            mu_posterior=1.10,
            sigma_posterior=0.06,
            n_observations=5,
        )
        await upsert_corner_capability(
            db_session,
            "laguna",
            1,
            "user-1",
            mu_posterior=0.85,
            sigma_posterior=0.08,
            n_observations=2,
        )
        await db_session.commit()

        barber_caps = await get_corner_capabilities(db_session, "barber", "user-1")
        laguna_caps = await get_corner_capabilities(db_session, "laguna", "user-1")
        assert barber_caps[1][0] > laguna_caps[1][0]

    @pytest.mark.asyncio
    async def test_multiple_corners(self, db_session: AsyncSession) -> None:
        for cn in [1, 3, 7, 10]:
            await upsert_corner_capability(
                db_session,
                "barber",
                cn,
                "user-1",
                mu_posterior=1.0 + cn * 0.01,
                sigma_posterior=0.10,
                n_observations=cn,
            )
        await db_session.commit()

        caps = await get_corner_capabilities(db_session, "barber", "user-1")
        assert set(caps.keys()) == {1, 3, 7, 10}
        assert caps[7][2] == 7  # n_observations == corner_number in this test
