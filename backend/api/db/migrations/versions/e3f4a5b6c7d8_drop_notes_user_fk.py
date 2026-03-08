"""Drop notes user_id foreign key constraint.

The users table is not populated for all auth methods (e.g., Google OAuth
via NextAuth). Other user-scoped tables use plain String for user_id.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the user_id FK constraint from notes."""
    op.drop_constraint("notes_user_id_fkey", "notes", type_="foreignkey")


def downgrade() -> None:
    """Re-add the user_id FK constraint."""
    op.create_foreign_key(
        "notes_user_id_fkey",
        "notes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
