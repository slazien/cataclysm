"""Add is_default column to equipment_profiles

Revision ID: f6b7c8d9e0a1
Revises: e535e52061ee
Create Date: 2026-03-06 22:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b7c8d9e0a1"
down_revision: str | Sequence[str] | None = "e535e52061ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_default boolean column to equipment_profiles."""
    op.add_column(
        "equipment_profiles",
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Remove is_default column."""
    op.drop_column("equipment_profiles", "is_default")
