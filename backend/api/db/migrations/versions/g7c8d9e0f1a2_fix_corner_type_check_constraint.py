"""Fix corner_type check constraint in track_corners_v2

The previous migration (e9f0a1b2c3d4) accidentally applied the character
values (brake/lift/flat/acceleration) to the corner_type column. This
migration replaces that constraint with the correct set of shape values.

Revision ID: g7c8d9e0f1a2
Revises: f6b7c8d9e0a1
Create Date: 2026-03-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "g7c8d9e0f1a2"
down_revision = "f6b7c8d9e0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the wrong constraint (if it exists)
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_corner_type"
    )
    # Add the correct constraint
    op.create_check_constraint(
        "ck_track_corners_v2_corner_type",
        "track_corners_v2",
        "corner_type IS NULL OR corner_type IN "
        "('sweeper', 'hairpin', 'chicane', 'kink', 'esses', 'carousel', 'complex')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_corner_type"
    )
    op.create_check_constraint(
        "ck_track_corners_v2_corner_type",
        "track_corners_v2",
        "corner_type IS NULL OR corner_type IN ('brake', 'lift', 'flat', 'acceleration')",
    )
