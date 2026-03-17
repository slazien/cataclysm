"""Add lap_tags table.

Revision ID: m3c4d5e6f7a8
Revises: l2b3c4d5e6f7
Create Date: 2026-03-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m3c4d5e6f7a8"
down_revision = "l2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lap_tags",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id", "lap_number", "tag"),
    )


def downgrade() -> None:
    op.drop_table("lap_tags")
