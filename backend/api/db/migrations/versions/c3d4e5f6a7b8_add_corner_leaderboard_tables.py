"""Add corner leaderboard tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-26 22:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    """Add corner_records and corner_kings tables, and leaderboard_opt_in column."""
    # Add leaderboard_opt_in to users
    op.add_column(
        "users",
        sa.Column("leaderboard_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Create corner_records table
    op.create_table(
        "corner_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("track_name", sa.String(), nullable=False),
        sa.Column("corner_number", sa.Integer(), nullable=False),
        sa.Column("min_speed_mps", sa.Float(), nullable=False),
        sa.Column("sector_time_s", sa.Float(), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_corner_records_track_corner",
        "corner_records",
        ["track_name", "corner_number"],
    )
    op.create_index("ix_corner_records_user", "corner_records", ["user_id"])
    op.create_index("ix_corner_records_track_name", "corner_records", ["track_name"])

    # Create corner_kings table
    op.create_table(
        "corner_kings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("track_name", sa.String(), nullable=False),
        sa.Column("corner_number", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("best_time_s", sa.Float(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_name", "corner_number"),
    )


def downgrade() -> None:
    """Remove corner leaderboard tables and leaderboard_opt_in column."""
    op.drop_table("corner_kings")
    op.drop_index("ix_corner_records_track_name", table_name="corner_records")
    op.drop_index("ix_corner_records_user", table_name="corner_records")
    op.drop_index("ix_corner_records_track_corner", table_name="corner_records")
    op.drop_table("corner_records")
    op.drop_column("users", "leaderboard_opt_in")
