"""Add corner_capability_factors table.

Revision ID: p6f7a8b9c0d1
Revises: o5e6f7a8b9c0
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6f7a8b9c0d1"
down_revision = "o5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corner_capability_factors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_slug", sa.String(), nullable=False),
        sa.Column("corner_number", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("mu_posterior", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("sigma_posterior", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("n_observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_slug", "corner_number", "user_id", name="uq_corner_capability"),
    )
    op.create_index("ix_corner_cap_track", "corner_capability_factors", ["track_slug"])


def downgrade() -> None:
    op.drop_index("ix_corner_cap_track", table_name="corner_capability_factors")
    op.drop_table("corner_capability_factors")
