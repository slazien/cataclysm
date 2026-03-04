"""Drop leaderboard_opt_in column from users

Revision ID: e4f5a6b7c8d9
Revises: a7b8c9d0e1f2
Create Date: 2026-03-03 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove the leaderboard_opt_in column — leaderboards are now always enabled."""
    op.drop_column("users", "leaderboard_opt_in")


def downgrade() -> None:
    """Re-add leaderboard_opt_in column with default False."""
    op.add_column(
        "users",
        sa.Column("leaderboard_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
