"""Add runtime settings table for live admin toggles.

Revision ID: k1a2b3c4d5e6
Revises: j0f1a2b3c4d5
Create Date: 2026-03-10 14:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k1a2b3c4d5e6"
down_revision = "j0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
