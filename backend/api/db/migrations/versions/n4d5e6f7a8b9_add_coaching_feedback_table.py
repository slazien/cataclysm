"""Add coaching_feedback table.

Revision ID: n4d5e6f7a8b9
Revises: m3c4d5e6f7a8
Create Date: 2026-03-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n4d5e6f7a8b9"
down_revision = "m3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coaching_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "user_id", "section", name="uq_feedback_per_section"),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
    )
    op.create_index("ix_coaching_feedback_session", "coaching_feedback", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_coaching_feedback_session", table_name="coaching_feedback")
    op.drop_table("coaching_feedback")
