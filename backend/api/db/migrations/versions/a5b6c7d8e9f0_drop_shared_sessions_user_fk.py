"""Drop shared_sessions user_id foreign key constraint.

The users table is not populated for all auth methods (e.g., Google OAuth
via NextAuth). All user-scoped tables must use plain String for user_id —
never ForeignKey("users.id").

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-03-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the user_id FK constraint from shared_sessions."""
    op.drop_constraint("shared_sessions_user_id_fkey", "shared_sessions", type_="foreignkey")


def downgrade() -> None:
    """Re-add the user_id FK constraint."""
    op.create_foreign_key(
        "shared_sessions_user_id_fkey",
        "shared_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
