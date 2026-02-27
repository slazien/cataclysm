"""merge achievement and leaderboard heads

Revision ID: 781e3b3a8108
Revises: 4fd348345278, c3d4e5f6a7b8
Create Date: 2026-02-26 22:32:09.152408

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "781e3b3a8108"
down_revision: str | Sequence[str] | None = ("4fd348345278", "c3d4e5f6a7b8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
