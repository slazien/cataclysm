"""Add track_slug and calibrated_mu columns to physics_cache for track-level caching.

Revision ID: c1d2e3f4a5b6
Revises: b9d0e1f2a3c4
Create Date: 2026-03-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b9d0e1f2a3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("physics_cache", sa.Column("track_slug", sa.String(64), nullable=True))
    op.add_column("physics_cache", sa.Column("calibrated_mu", sa.String(8), nullable=True))
    op.create_index("ix_physics_cache_track_slug", "physics_cache", ["track_slug"])
    op.create_unique_constraint(
        "uq_physics_cache_track_key",
        "physics_cache",
        ["track_slug", "endpoint", "profile_id", "calibrated_mu"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_physics_cache_track_key", "physics_cache", type_="unique")
    op.drop_index("ix_physics_cache_track_slug", table_name="physics_cache")
    op.drop_column("physics_cache", "calibrated_mu")
    op.drop_column("physics_cache", "track_slug")
