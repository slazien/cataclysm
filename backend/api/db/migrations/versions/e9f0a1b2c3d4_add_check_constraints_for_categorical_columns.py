"""Add CHECK constraints for categorical columns on tracks and track_corners_v2.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-03-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# -- tracks table constraints --------------------------------------------------

_TRACKS_CONSTRAINTS = {
    "ck_tracks_status": ("status IN ('draft', 'published', 'archived')"),
    "ck_tracks_direction_of_travel": (
        "direction_of_travel IS NULL OR "
        "direction_of_travel IN ('clockwise', 'counter-clockwise', 'both')"
    ),
    "ck_tracks_track_type": (
        "track_type IS NULL OR track_type IN ('circuit', 'hillclimb', 'street', 'oval', 'kart')"
    ),
}

# -- track_corners_v2 table constraints ----------------------------------------

_CORNERS_CONSTRAINTS = {
    "ck_track_corners_v2_character": (
        "character IS NULL OR "
        "character IN ('hairpin', 'sweeper', 'chicane', 'kink', 'esses', "
        "'carousel', 'complex')"
    ),
    "ck_track_corners_v2_direction": ("direction IS NULL OR direction IN ('left', 'right')"),
    "ck_track_corners_v2_corner_type": (
        "corner_type IS NULL OR corner_type IN ('brake', 'lift', 'flat', 'acceleration')"
    ),
    "ck_track_corners_v2_elevation_trend": (
        "elevation_trend IS NULL OR "
        "elevation_trend IN ('uphill', 'downhill', 'flat', 'crest', 'compression')"
    ),
    "ck_track_corners_v2_camber": (
        "camber IS NULL OR camber IN ('positive', 'negative', 'off-camber', 'flat', 'transitions')"
    ),
}


def upgrade() -> None:
    for name, expr in _TRACKS_CONSTRAINTS.items():
        op.create_check_constraint(name, "tracks", expr)
    for name, expr in _CORNERS_CONSTRAINTS.items():
        op.create_check_constraint(name, "track_corners_v2", expr)


def downgrade() -> None:
    for name in reversed(list(_CORNERS_CONSTRAINTS)):
        op.drop_constraint(name, "track_corners_v2", type_="check")
    for name in reversed(list(_TRACKS_CONSTRAINTS)):
        op.drop_constraint(name, "tracks", type_="check")
