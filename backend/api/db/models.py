"""SQLAlchemy 2.0 async ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Session(Base):
    """A telemetry session uploaded from RaceChrono."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    n_laps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_clean_laps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_lap_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    top3_avg_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_lap_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    coaching_reports: Mapped[list[CoachingReport]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    coaching_contexts: Mapped[list[CoachingContext]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_sessions_track_name", "track_name"),)


class CoachingReport(Base):
    """AI-generated coaching report for a session."""

    __tablename__ = "coaching_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    skill_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    session: Mapped[Session] = relationship(back_populates="coaching_reports")


class CoachingContext(Base):
    """Conversation context for follow-up coaching chat."""

    __tablename__ = "coaching_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    messages_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    session: Mapped[Session] = relationship(back_populates="coaching_contexts")
