"""Achievement evaluation engine.

Defines seed achievements and evaluates criteria to unlock badges.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import (
    AchievementDefinition,
    CoachingReport,
    Session,
    UserAchievement,
)

logger = logging.getLogger(__name__)

_seeded = False

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_ACHIEVEMENTS: list[dict[str, object]] = [
    # ── Milestones (session count) ──────────────────────────────────────
    {
        "id": "first_session",
        "name": "First Laps",
        "description": "Upload your first session",
        "criteria_type": "session_count",
        "criteria_value": 1,
        "tier": "bronze",
        "icon": "trophy",
        "category": "milestones",
    },
    {
        "id": "five_sessions",
        "name": "Regular",
        "description": "Upload 5 sessions",
        "criteria_type": "session_count",
        "criteria_value": 5,
        "tier": "bronze",
        "icon": "calendar",
        "category": "milestones",
    },
    {
        "id": "track_rat_10",
        "name": "Track Rat",
        "description": "Upload 10 sessions",
        "criteria_type": "session_count",
        "criteria_value": 10,
        "tier": "silver",
        "icon": "flame",
        "category": "milestones",
    },
    {
        "id": "track_veteran",
        "name": "Track Veteran",
        "description": "Upload 25 sessions",
        "criteria_type": "session_count",
        "criteria_value": 25,
        "tier": "gold",
        "icon": "award",
        "category": "milestones",
    },
    {
        "id": "track_addict",
        "name": "Track Addict",
        "description": "Upload 50 sessions",
        "criteria_type": "session_count",
        "criteria_value": 50,
        "tier": "platinum",
        "icon": "crown",
        "category": "milestones",
    },
    # ── Laps (total lap count) ──────────────────────────────────────────
    {
        "id": "century_laps",
        "name": "Century",
        "description": "Complete 100 total laps",
        "criteria_type": "total_laps",
        "criteria_value": 100,
        "tier": "bronze",
        "icon": "repeat",
        "category": "laps",
    },
    {
        "id": "laps_250",
        "name": "Quarter Thousand",
        "description": "Complete 250 total laps",
        "criteria_type": "total_laps",
        "criteria_value": 250,
        "tier": "silver",
        "icon": "layers",
        "category": "laps",
    },
    {
        "id": "laps_500",
        "name": "500 Club",
        "description": "Complete 500 total laps",
        "criteria_type": "total_laps",
        "criteria_value": 500,
        "tier": "gold",
        "icon": "hash",
        "category": "laps",
    },
    {
        "id": "laps_1000",
        "name": "Iron Lapper",
        "description": "Complete 1,000 total laps",
        "criteria_type": "total_laps",
        "criteria_value": 1000,
        "tier": "platinum",
        "icon": "infinity",
        "category": "laps",
    },
    # ── Consistency (score threshold) ───────────────────────────────────
    {
        "id": "consistent_driver",
        "name": "Getting Dialed In",
        "description": "Achieve a consistency score above 70",
        "criteria_type": "score_threshold",
        "criteria_value": 70,
        "tier": "bronze",
        "icon": "gauge",
        "category": "consistency",
    },
    {
        "id": "consistency_king",
        "name": "Consistency King",
        "description": "Achieve a consistency score above 85",
        "criteria_type": "score_threshold",
        "criteria_value": 85,
        "tier": "silver",
        "icon": "target",
        "category": "consistency",
    },
    {
        "id": "metronomic",
        "name": "Metronomic",
        "description": "Achieve a consistency score above 90",
        "criteria_type": "score_threshold",
        "criteria_value": 90,
        "tier": "gold",
        "icon": "crosshair",
        "category": "consistency",
    },
    # ── Braking ─────────────────────────────────────────────────────────
    {
        "id": "brake_master",
        "name": "Brake Master",
        "description": "Get an A grade on braking in every corner",
        "criteria_type": "all_grades_a",
        "criteria_value": 0,
        "tier": "gold",
        "icon": "zap",
        "category": "braking",
    },
    # ── Trail Braking ───────────────────────────────────────────────────
    {
        "id": "smooth_operator",
        "name": "Smooth Operator",
        "description": "Get B+ or better on trail braking in every corner",
        "criteria_type": "all_grades_b_plus",
        "criteria_value": 0,
        "tier": "silver",
        "icon": "wind",
        "category": "trail_braking",
    },
    {
        "id": "trail_wizard",
        "name": "Trail Wizard",
        "description": "Get an A grade on trail braking in every corner",
        "criteria_type": "all_trail_grades_a",
        "criteria_value": 0,
        "tier": "gold",
        "icon": "sparkles",
        "category": "trail_braking",
    },
    # ── Exploration (track diversity) ───────────────────────────────────
    {
        "id": "multi_track",
        "name": "Track Explorer",
        "description": "Drive at 3 different tracks",
        "criteria_type": "track_count",
        "criteria_value": 3,
        "tier": "bronze",
        "icon": "map-pin",
        "category": "exploration",
    },
    {
        "id": "globetrotter",
        "name": "Globetrotter",
        "description": "Drive at 5 different tracks",
        "criteria_type": "track_count",
        "criteria_value": 5,
        "tier": "silver",
        "icon": "compass",
        "category": "exploration",
    },
    {
        "id": "track_nomad",
        "name": "Track Nomad",
        "description": "Drive at 10 different tracks",
        "criteria_type": "track_count",
        "criteria_value": 10,
        "tier": "gold",
        "icon": "globe",
        "category": "exploration",
    },
]


async def seed_achievements(db: AsyncSession) -> None:
    """Insert or update seed achievement definitions."""
    global _seeded  # noqa: PLW0603
    if _seeded:
        return

    existing_result = await db.execute(select(AchievementDefinition))
    existing_map: dict[str, AchievementDefinition] = {
        row.id: row for row in existing_result.scalars().all()
    }

    for defn in SEED_ACHIEVEMENTS:
        existing = existing_map.get(str(defn["id"]))
        if existing is None:
            db.add(AchievementDefinition(**defn))
        else:
            # Sync mutable fields (category, name, description, icon, tier)
            for field in ("category", "name", "description", "icon", "tier", "criteria_type"):
                if getattr(existing, field) != defn.get(field):
                    setattr(existing, field, defn[field])

    await db.flush()
    _seeded = True


async def check_achievements(
    db: AsyncSession, user_id: str, session_id: str | None = None
) -> list[str]:
    """Evaluate all achievements for a user, returning newly unlocked IDs."""
    await seed_achievements(db)

    result = await db.execute(
        select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
    )
    already_unlocked = {row[0] for row in result.all()}

    defn_result = await db.execute(select(AchievementDefinition))
    definitions: list[AchievementDefinition] = list(defn_result.scalars().all())

    newly_unlocked: list[str] = []
    for defn in definitions:
        if defn.id in already_unlocked:
            continue
        if await _check_criteria(db, user_id, session_id, defn):
            db.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_id=defn.id,
                    session_id=session_id,
                    unlocked_at=datetime.now(UTC),
                    is_new=True,
                )
            )
            newly_unlocked.append(defn.id)

    if newly_unlocked:
        await db.flush()
        logger.info("User %s unlocked: %s", user_id, newly_unlocked)

    return newly_unlocked


async def _check_criteria(
    db: AsyncSession,
    user_id: str,
    session_id: str | None,
    defn: AchievementDefinition,
) -> bool:
    """Evaluate a single achievement's criteria."""
    ct = defn.criteria_type
    cv = defn.criteria_value

    if ct == "session_count":
        result = await db.execute(
            select(func.count()).select_from(Session).where(Session.user_id == user_id)
        )
        count = result.scalar() or 0
        return count >= cv

    if ct == "score_threshold":
        result = await db.execute(
            select(func.max(Session.consistency_score)).where(Session.user_id == user_id)
        )
        best = result.scalar()
        return best is not None and best >= cv

    if ct == "track_count":
        result = await db.execute(
            select(func.count(func.distinct(Session.track_name))).where(Session.user_id == user_id)
        )
        count = result.scalar() or 0
        return count >= cv

    if ct == "total_laps":
        result = await db.execute(
            select(func.sum(Session.n_laps)).where(Session.user_id == user_id)
        )
        total = result.scalar() or 0
        return total >= cv

    if ct == "all_grades_a":
        return await _check_all_grades(db, session_id, "braking", {"A", "A+"})

    if ct == "all_grades_b_plus":
        return await _check_all_grades(db, session_id, "trail_braking", {"A+", "A", "A-", "B+"})

    if ct == "all_trail_grades_a":
        return await _check_all_grades(db, session_id, "trail_braking", {"A", "A+"})

    return False


async def _check_all_grades(
    db: AsyncSession,
    session_id: str | None,
    dimension: str,
    passing_grades: set[str],
) -> bool:
    """Check if all corners in a coaching report meet the grade threshold."""
    if session_id is None:
        return False

    result = await db.execute(
        select(CoachingReport.report_json)
        .where(CoachingReport.session_id == session_id)
        .order_by(CoachingReport.created_at.desc())
        .limit(1)
    )
    row = result.scalar()
    if row is None:
        return False

    corner_grades = row.get("corner_grades", [])
    if not corner_grades:
        return False

    return all(cg.get(dimension, "C") in passing_grades for cg in corner_grades)


async def get_user_achievements(db: AsyncSession, user_id: str) -> list[dict[str, object]]:
    """Return all achievements with unlock status for a user."""
    await seed_achievements(db)

    defn_result = await db.execute(select(AchievementDefinition))
    definitions: list[AchievementDefinition] = list(defn_result.scalars().all())

    ua_result = await db.execute(select(UserAchievement).where(UserAchievement.user_id == user_id))
    unlocked_map: dict[str, UserAchievement] = {
        ua.achievement_id: ua for ua in ua_result.scalars().all()
    }

    achievements: list[dict[str, object]] = []
    for defn in definitions:
        ua = unlocked_map.get(defn.id)
        achievements.append(
            {
                "id": defn.id,
                "name": defn.name,
                "description": defn.description,
                "criteria_type": defn.criteria_type,
                "criteria_value": defn.criteria_value,
                "tier": defn.tier,
                "icon": defn.icon,
                "category": defn.category,
                "unlocked": ua is not None,
                "session_id": ua.session_id if ua else None,
                "unlocked_at": ua.unlocked_at.isoformat() if ua else None,
            }
        )

    return achievements


async def get_recent_achievements(db: AsyncSession, user_id: str) -> list[dict[str, object]]:
    """Return newly unlocked achievements and mark them as seen."""
    join_result = await db.execute(
        select(UserAchievement, AchievementDefinition)
        .join(AchievementDefinition, UserAchievement.achievement_id == AchievementDefinition.id)
        .where(UserAchievement.user_id == user_id, UserAchievement.is_new.is_(True))
    )
    rows = join_result.all()

    achievements: list[dict[str, object]] = []
    for row in rows:
        ua: UserAchievement = row[0]  # type: ignore[assignment]
        defn: AchievementDefinition = row[1]  # type: ignore[assignment]
        achievements.append(
            {
                "id": defn.id,
                "name": defn.name,
                "description": defn.description,
                "criteria_type": defn.criteria_type,
                "criteria_value": defn.criteria_value,
                "tier": defn.tier,
                "icon": defn.icon,
                "category": defn.category,
                "unlocked": True,
                "session_id": ua.session_id,
                "unlocked_at": ua.unlocked_at.isoformat(),
            }
        )
        ua.is_new = False

    await db.flush()
    return achievements
