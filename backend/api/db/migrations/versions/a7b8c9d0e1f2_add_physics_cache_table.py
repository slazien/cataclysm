"""Add physics_cache table for persistent velocity solver results.

Revision ID: a7b8c9d0e1f2
Revises: f6b7c8d9e0a1
Create Date: 2026-03-07

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6b7c8d9e0a1"
branch_labels = None
depends_on = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "physics_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), server_default="", nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("code_version", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "endpoint", "profile_id", name="uq_physics_cache_key"),
    )
    op.create_index("ix_physics_cache_session", "physics_cache", ["session_id"])
    op.create_index("ix_physics_cache_profile", "physics_cache", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_physics_cache_profile", table_name="physics_cache")
    op.drop_index("ix_physics_cache_session", table_name="physics_cache")
    op.drop_table("physics_cache")
