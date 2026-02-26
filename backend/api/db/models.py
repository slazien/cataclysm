"""SQLAlchemy 2.0 async ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class User(Base):
    """An authenticated user (Google OAuth)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Google sub
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    skill_level: Mapped[str] = mapped_column(String, default="intermediate")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """A telemetry session uploaded from RaceChrono."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
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
    user: Mapped[User | None] = relationship(back_populates="sessions")
    coaching_reports: Mapped[list[CoachingReport]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    coaching_contexts: Mapped[list[CoachingContext]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    session_file: Mapped[SessionFile | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ix_sessions_track_name", "track_name"),
        Index("ix_sessions_user_id", "user_id"),
    )


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


class SessionFile(Base):
    """Raw CSV file stored for session replay after restart."""

    __tablename__ = "session_files"

    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    csv_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    session: Mapped[Session] = relationship(back_populates="session_file")


class EquipmentProfileDB(Base):
    """Equipment profile persisted in PostgreSQL."""

    __tablename__ = "equipment_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    profile_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User | None] = relationship()
    session_assignments: Mapped[list[SessionEquipmentDB]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class SessionEquipmentDB(Base):
    """Session-equipment assignment persisted in PostgreSQL."""

    __tablename__ = "session_equipment_assignments"

    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("equipment_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    assignment_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    session: Mapped[Session] = relationship()
    profile: Mapped[EquipmentProfileDB] = relationship(back_populates="session_assignments")
