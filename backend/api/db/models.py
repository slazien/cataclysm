"""SQLAlchemy 2.0 async ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    role: Mapped[str] = mapped_column(String, default="driver")  # driver | instructor
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
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
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


class AchievementDefinition(Base):
    """A badge/achievement that can be unlocked."""

    __tablename__ = "achievement_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    criteria_type: Mapped[str] = mapped_column(String, nullable=False)
    criteria_value: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)  # bronze / silver / gold / platinum
    icon: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, server_default="milestones")


class UserAchievement(Base):
    """Tracks which achievements a user has unlocked."""

    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[str] = mapped_column(
        String, ForeignKey("achievement_definitions.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("user_id", "achievement_id"),)


class CornerRecord(Base):
    """A user's recorded time through a specific corner."""

    __tablename__ = "corner_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    corner_number: Mapped[int] = mapped_column(Integer, nullable=False)
    min_speed_mps: Mapped[float] = mapped_column(Float, nullable=False)
    sector_time_s: Mapped[float] = mapped_column(Float, nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    brake_point_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_corner_records_track_corner", "track_name", "corner_number"),
        Index("ix_corner_records_user", "user_id"),
    )


class CornerKing(Base):
    """Current 'King of the Corner' for each corner on a track."""

    __tablename__ = "corner_kings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    corner_number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    best_time_s: Mapped[float] = mapped_column(Float, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("track_name", "corner_number"),)


class SharedSession(Base):
    """A share token allowing a friend to upload their session for comparison."""

    __tablename__ = "shared_sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    session: Mapped[Session] = relationship()
    comparison_reports: Mapped[list[ShareComparisonReport]] = relationship(
        back_populates="shared_session", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_shared_sessions_user_id", "user_id"),)


class ShareComparisonReport(Base):
    """Comparison result generated when a friend uploads to a share link."""

    __tablename__ = "share_comparison_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_token: Mapped[str] = mapped_column(
        String,
        ForeignKey("shared_sessions.token", ondelete="CASCADE"),
        nullable=False,
    )
    challenger_session_id: Mapped[str] = mapped_column(String, nullable=False)
    report_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_comparison_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    shared_session: Mapped[SharedSession] = relationship(back_populates="comparison_reports")


class InstructorStudent(Base):
    """Instructor-student link with invite code support."""

    __tablename__ = "instructor_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instructor_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    invite_code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("instructor_id", "student_id"),
        Index("ix_instructor_students_instructor", "instructor_id"),
    )


class StudentFlag(Base):
    """A flag (auto or manual) for a student's session."""

    __tablename__ = "student_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    flag_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organization(Base):
    """An HPDE organization / club."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgMembership(Base):
    """Membership in an organization."""

    __tablename__ = "org_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # owner | instructor | student
    run_group: Mapped[str | None] = mapped_column(String, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("org_id", "user_id"),)


class OrgEvent(Base):
    """A scheduled event by an organization."""

    __tablename__ = "org_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_groups: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NoteDB(Base):
    """User-created note, optionally anchored to a session and/or data point."""

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=True
    )
    anchor_type: Mapped[str | None] = mapped_column(String, nullable=True)
    anchor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    anchor_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships (user_id has no FK — users table not populated for OAuth)
    # No user relationship — user_id is plain String without FK
    session: Mapped[Session | None] = relationship()

    __table_args__ = (
        Index("ix_notes_user_session", "user_id", "session_id"),
        Index("ix_notes_user_global", "user_id"),
    )


class StickyDB(Base):
    """Placeable sticky note positioned anywhere in the app UI."""

    __tablename__ = "stickies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    pos_x: Mapped[float] = mapped_column(Float, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False)
    content: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    tone: Mapped[str] = mapped_column(String, server_default="amber", nullable=False)
    collapsed: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    view_scope: Mapped[str] = mapped_column(String, server_default="global", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_stickies_user", "user_id"),)


class TrackCornerConfig(Base):
    """Admin-edited corner positions for a track, stored as JSONB."""

    __tablename__ = "track_corner_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    corners_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str] = mapped_column(String(200), nullable=False)


class Track(Base):
    """Track metadata — the core of the v2 track data pipeline."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, server_default="[]", nullable=False)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_range_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_tier: Mapped[int] = mapped_column(SmallInteger, server_default="1", nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="draft", nullable=False)
    centerline_geojson: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    direction_of_travel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    track_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    verified_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_tracks_status",
        ),
        CheckConstraint(
            "direction_of_travel IS NULL OR "
            "direction_of_travel IN ('clockwise', 'counter-clockwise', 'both')",
            name="ck_tracks_direction_of_travel",
        ),
        CheckConstraint(
            "track_type IS NULL OR "
            "track_type IN ('circuit', 'hillclimb', 'street', 'oval', 'kart')",
            name="ck_tracks_track_type",
        ),
    )


class TrackCornerV2(Base):
    """Per-corner data for a track (normalized rows replacing JSONB blob)."""

    __tablename__ = "track_corners_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fraction: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    character: Mapped[str | None] = mapped_column(String(10), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    corner_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    elevation_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    camber: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blind: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    coaching_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_detected: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, server_default="0.0", nullable=False)
    detection_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relationship
    track: Mapped[Track] = relationship()

    __table_args__ = (
        UniqueConstraint("track_id", "number"),
        Index("ix_track_corners_v2_track_id", "track_id"),
        CheckConstraint(
            "character IS NULL OR character IN ('flat', 'lift', 'brake')",
            name="ck_track_corners_v2_character",
        ),
        CheckConstraint(
            "direction IS NULL OR direction IN ('left', 'right')",
            name="ck_track_corners_v2_direction",
        ),
        CheckConstraint(
            "corner_type IS NULL OR "
            "corner_type IN ('sweeper', 'hairpin', 'chicane', 'kink', 'esses', "
            "'carousel', 'complex')",
            name="ck_track_corners_v2_corner_type",
        ),
        CheckConstraint(
            "elevation_trend IS NULL OR "
            "elevation_trend IN ('uphill', 'downhill', 'flat', 'crest', 'compression')",
            name="ck_track_corners_v2_elevation_trend",
        ),
        CheckConstraint(
            "camber IS NULL OR "
            "camber IN ('positive', 'negative', 'off-camber', 'flat', 'transitions')",
            name="ck_track_corners_v2_camber",
        ),
    )


class TrackLandmark(Base):
    """Visual reference landmark for a track."""

    __tablename__ = "track_landmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    landmark_type: Mapped[str] = mapped_column(String(20), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, server_default="1.0", nullable=False)

    # Relationship
    track: Mapped[Track] = relationship()

    __table_args__ = (Index("ix_track_landmarks_track_id", "track_id"),)


class TrackElevationProfile(Base):
    """Elevation profile for a track from a specific source."""

    __tablename__ = "track_elevation_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    distances_m: Mapped[list] = mapped_column(JSONB, nullable=False)
    elevations_m: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    track: Mapped[Track] = relationship()

    __table_args__ = (
        UniqueConstraint("track_id", "source"),
        Index("ix_track_elevation_profiles_track_id", "track_id"),
    )


class TrackEnrichmentLog(Base):
    """Audit trail entry for track enrichment pipeline steps."""

    __tablename__ = "track_enrichment_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    track: Mapped[Track] = relationship()

    __table_args__ = (Index("ix_track_enrichment_log_track_id", "track_id"),)


class PhysicsCacheEntry(Base):
    """Persistent cache for physics computation results (optimal profile/comparison).

    Survives backend restarts and Railway deploys.  Keyed by session, endpoint,
    and equipment profile.  A ``code_version`` column enables bulk invalidation
    when the physics algorithm changes.
    """

    __tablename__ = "physics_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)  # "profile" | "comparison"
    profile_id: Mapped[str] = mapped_column(
        String, nullable=False, server_default=""
    )  # "" = no equipment
    track_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calibrated_mu: Mapped[str | None] = mapped_column(String(8), nullable=True)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    code_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "endpoint", "profile_id", name="uq_physics_cache_key"),
        UniqueConstraint(
            "track_slug",
            "endpoint",
            "profile_id",
            "calibrated_mu",
            name="uq_physics_cache_track_key",
        ),
        Index("ix_physics_cache_session", "session_id"),
        Index("ix_physics_cache_profile", "profile_id"),
        Index("ix_physics_cache_track_slug", "track_slug"),
    )


class LLMUsageEvent(Base):
    """Persisted LLM usage event for cost and reliability analytics."""

    __tablename__ = "llm_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    task: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cache_creation_input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_llm_usage_events_event_timestamp", "event_timestamp"),
        Index("ix_llm_usage_events_task", "task"),
        Index("ix_llm_usage_events_provider", "provider"),
    )


class RuntimeSetting(Base):
    """Runtime-tunable application settings persisted in Postgres."""

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmTaskRoute(Base):
    """Per-task LLM routing configuration persisted in Postgres."""

    __tablename__ = "llm_task_routes"

    task: Mapped[str] = mapped_column(String(100), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CoachingFeedback(Base):
    """User thumbs-up/down feedback on coaching report sections."""

    __tablename__ = "coaching_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    section: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", "section", name="uq_feedback_per_section"),
        CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
        Index("ix_coaching_feedback_session", "session_id"),
    )


class LapTag(Base):
    """Per-lap user tag for exclusion marking. Composite PK."""

    __tablename__ = "lap_tags"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    lap_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
