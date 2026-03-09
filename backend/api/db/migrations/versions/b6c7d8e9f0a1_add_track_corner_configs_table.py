"""Add track_corner_configs table for admin-edited corner positions.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-03-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "track_corner_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_slug", sa.String(100), nullable=False),
        sa.Column("corners_json", JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_by", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_track_corner_configs_track_slug",
        "track_corner_configs",
        ["track_slug"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_track_corner_configs_track_slug", table_name="track_corner_configs")
    op.drop_table("track_corner_configs")
