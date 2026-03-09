"""Add track_corners_v2, track_landmarks, elevation_profiles, enrichment_log tables.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-03-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- track_corners_v2 ---
    op.create_table(
        "track_corners_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("fraction", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("character", sa.String(10), nullable=True),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("corner_type", sa.String(20), nullable=True),
        sa.Column("elevation_trend", sa.String(20), nullable=True),
        sa.Column("camber", sa.String(20), nullable=True),
        sa.Column("blind", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("coaching_notes", sa.Text(), nullable=True),
        sa.Column("auto_detected", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("detection_method", sa.String(30), nullable=True),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_id", "number"),
    )
    op.create_index("ix_track_corners_v2_track_id", "track_corners_v2", ["track_id"])

    # --- track_landmarks ---
    op.create_table(
        "track_landmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("landmark_type", sa.String(20), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_landmarks_track_id", "track_landmarks", ["track_id"])

    # --- track_elevation_profiles ---
    op.create_table(
        "track_elevation_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("distances_m", JSONB(), nullable=False),
        sa.Column("elevations_m", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_id", "source"),
    )
    op.create_index(
        "ix_track_elevation_profiles_track_id", "track_elevation_profiles", ["track_id"]
    )

    # --- track_enrichment_log ---
    op.create_table(
        "track_enrichment_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_enrichment_log_track_id", "track_enrichment_log", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_track_enrichment_log_track_id", table_name="track_enrichment_log")
    op.drop_table("track_enrichment_log")
    op.drop_index("ix_track_elevation_profiles_track_id", table_name="track_elevation_profiles")
    op.drop_table("track_elevation_profiles")
    op.drop_index("ix_track_landmarks_track_id", table_name="track_landmarks")
    op.drop_table("track_landmarks")
    op.drop_index("ix_track_corners_v2_track_id", table_name="track_corners_v2")
    op.drop_table("track_corners_v2")
