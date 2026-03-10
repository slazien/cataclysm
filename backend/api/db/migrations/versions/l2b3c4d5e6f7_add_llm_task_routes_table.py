"""Add llm_task_routes table.

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
Create Date: 2026-03-10 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l2b3c4d5e6f7"
down_revision = "k1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_task_routes",
        sa.Column("task", sa.String(length=100), nullable=False),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("task"),
    )


def downgrade() -> None:
    op.drop_table("llm_task_routes")
