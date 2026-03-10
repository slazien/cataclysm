"""Merge branch heads and fix corner_type check constraint.

The e9f0a1b2c3d4 branch applied the wrong CHECK constraint to
track_corners_v2.corner_type (used character values instead of shape values).
This migration merges both heads and corrects the constraint.

Revision ID: h8d9e0f1a2b3
Revises: e9f0a1b2c3d4, g7c8d9e0f1a2
Create Date: 2026-03-10 01:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "h8d9e0f1a2b3"
down_revision = ("e9f0a1b2c3d4", "g7c8d9e0f1a2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # After merging both branches the constraint may be in the wrong state
    # (from e9f0a1b2c3d4 which incorrectly set corner_type to brake/lift/flat/acceleration).
    # g7c8d9e0f1a2 already fixed it on its own branch; this migration re-applies
    # the correct constraint unconditionally so both upgrade paths end up consistent.
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_corner_type"
    )
    op.create_check_constraint(
        "ck_track_corners_v2_corner_type",
        "track_corners_v2",
        "corner_type IS NULL OR corner_type IN "
        "('sweeper', 'hairpin', 'chicane', 'kink', 'esses', 'carousel', 'complex')",
    )


def downgrade() -> None:
    # Cannot meaningfully un-merge, just leave constraint in correct state
    pass
