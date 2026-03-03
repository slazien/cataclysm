"""Add ai_comparison_text to share_comparison_reports

Revision ID: a7b8c9d0e1f2
Revises: f5a9c2b7d301
Create Date: 2026-03-03 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f5a9c2b7d301"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ai_comparison_text nullable column to share_comparison_reports."""
    op.add_column(
        "share_comparison_reports",
        sa.Column("ai_comparison_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove ai_comparison_text from share_comparison_reports."""
    op.drop_column("share_comparison_reports", "ai_comparison_text")
