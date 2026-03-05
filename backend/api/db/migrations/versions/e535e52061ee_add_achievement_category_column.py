"""Add achievement category column

Revision ID: e535e52061ee
Revises: f5a9c2b7d301
Create Date: 2026-03-05 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e535e52061ee"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add category column to achievement_definitions."""
    op.add_column(
        "achievement_definitions",
        sa.Column("category", sa.String(), server_default="milestones", nullable=False),
    )


def downgrade() -> None:
    """Remove category column."""
    op.drop_column("achievement_definitions", "category")
