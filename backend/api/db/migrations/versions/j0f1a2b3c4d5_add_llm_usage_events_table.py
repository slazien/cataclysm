"""Add persistent LLM usage telemetry table.

Revision ID: j0f1a2b3c4d5
Revises: i9e0f1a2b3c4
Create Date: 2026-03-10 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j0f1a2b3c4d5"
down_revision = "i9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_creation_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("error", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_usage_events_event_timestamp",
        "llm_usage_events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index("ix_llm_usage_events_task", "llm_usage_events", ["task"], unique=False)
    op.create_index(
        "ix_llm_usage_events_provider",
        "llm_usage_events",
        ["provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_events_provider", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_task", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_event_timestamp", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
