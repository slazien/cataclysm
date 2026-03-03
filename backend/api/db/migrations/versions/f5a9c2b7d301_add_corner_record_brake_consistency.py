"""Add brake_point_m and consistency_cv to corner_records

Revision ID: f5a9c2b7d301
Revises: 8feb700a204a
Create Date: 2026-03-02 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a9c2b7d301"
down_revision: str | Sequence[str] | None = "8feb700a204a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add brake_point_m and consistency_cv nullable columns to corner_records."""
    op.add_column(
        "corner_records",
        sa.Column("brake_point_m", sa.Float(), nullable=True),
    )
    op.add_column(
        "corner_records",
        sa.Column("consistency_cv", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove brake_point_m and consistency_cv from corner_records."""
    op.drop_column("corner_records", "consistency_cv")
    op.drop_column("corner_records", "brake_point_m")
