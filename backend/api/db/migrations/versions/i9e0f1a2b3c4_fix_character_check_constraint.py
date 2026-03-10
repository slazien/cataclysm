"""Fix character CHECK constraint on track_corners_v2.

The e9f0a1b2c3d4 migration set ck_track_corners_v2_character to shape
values (hairpin/sweeper/...) instead of the correct character values
(flat/lift/brake). h8d9e0f1a2b3 only fixed corner_type; this fixes character.

Revision ID: i9e0f1a2b3c4
Revises: h8d9e0f1a2b3
Create Date: 2026-03-10 02:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "i9e0f1a2b3c4"
down_revision = "h8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_character"
    )
    op.create_check_constraint(
        "ck_track_corners_v2_character",
        "track_corners_v2",
        "character IS NULL OR character IN ('flat', 'lift', 'brake')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE track_corners_v2 DROP CONSTRAINT IF EXISTS ck_track_corners_v2_character"
    )
    op.create_check_constraint(
        "ck_track_corners_v2_character",
        "track_corners_v2",
        "character IS NULL OR character IN "
        "('hairpin', 'sweeper', 'chicane', 'kink', 'esses', 'carousel', 'complex')",
    )
