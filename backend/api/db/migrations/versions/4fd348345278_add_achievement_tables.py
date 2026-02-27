"""Add achievement tables

Revision ID: 4fd348345278
Revises: b2c3d4e5f6a7
Create Date: 2026-02-26 21:12:04.195826

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4fd348345278"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "achievement_definitions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("criteria_type", sa.String(), nullable=False),
        sa.Column("criteria_value", sa.Float(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("achievement_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["achievement_id"],
            ["achievement_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "achievement_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_achievements")
    op.drop_table("achievement_definitions")
