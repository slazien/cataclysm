"""Merge branch heads and fix swapped CHECK constraints on track_corners_v2.

The e9f0a1b2c3d4 migration accidentally swapped the constraint values:
- ck_track_corners_v2_character got corner_type shape values (hairpin/sweeper/...)
- ck_track_corners_v2_corner_type got character values (brake/lift/flat/acceleration)

Both constraints are corrected here unconditionally (DROP IF EXISTS + re-create).

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
    # Fix character constraint (was accidentally set to corner_type shape values)
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_character"
    )
    op.create_check_constraint(
        "ck_track_corners_v2_character",
        "track_corners_v2",
        "character IS NULL OR character IN ('flat', 'lift', 'brake')",
    )
    # Fix corner_type constraint (was accidentally set to character values)
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
    # Cannot meaningfully un-merge; leave constraints in correct state
    pass
