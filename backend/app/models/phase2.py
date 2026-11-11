"""Phase 2 domain model: Organization / Planning Cycle / Resources / Calendar.

Design principles (from 05_DOMAIN_MODEL_AND_DATABASE.md + 06_UNIT_INPUT):
- Every relationship is FK-enforced (no JSON-ID sourcing of truth).
- Resources are canonical, organization-wide (rooms + instructors); units
  never duplicate them. Per-project availability/commitments are separate rows
  so a shared resource keeps a single identity while each Planning Cycle holds
  its own schedule windows.
- Cohort is a stable *group/entry* belonging to a Unit; per-cycle expected
  enrollment lives on CycleCohort (never duplicated on CourseOffering).
- CourseOffering is per-PlanningCycle; it can serve several Units and Cohorts
  through normalized join tables (OfferingUnit / OfferingCohort).
- No auto-merge: linking a proposed resource to an existing canonical one is an
  explicit server-side operation (Q5 pending).
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanningCycle(Base):
    """A named planning window (e.g. a term/semester) that several Units join.

    Multiple cycles may share the same term label; nothing auto-dedupes them
    (05: "don't forbid several plans just because the term is the same").
    """

    __tablename__ = "planning_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # nullable; backend normalizes empty/blank to None and treats it as "no label"
    term: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # e.g. "draft" | "open" | "submitted" | "reviewed" | "published"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    # Academic-window bounds for the cycle (date only)
    start_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
    # Logical-delete timestamp (NULL = active). Soft-delete preserves audit history.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_planning_cycles_org_name"),
        Index("ix_planning_cycles_organization_id", "organization_id"),
    )

    units: Mapped[list["CycleUnit"]] = relationship(
        "CycleUnit", back_populates="cycle", cascade="all, delete-orphan"
    )
    courses: Mapped[list["CourseOffering"]] = relationship(
        "CourseOffering", back_populates="planning_cycle", cascade="all, delete-orphan"
    )


class Unit(Base):
    """A stable organizational group (e.g. a teaching department)."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_units_org_name"),
        Index("ix_units_organization_id", "organization_id"),
    )

    memberships: Mapped[list["CycleUnit"]] = relationship(
        "CycleUnit", back_populates="unit", cascade="all, delete-orphan"
    )


class CycleUnit(Base):
    """Join table: a Unit participates in a PlanningCycle."""

    __tablename__ = "cycle_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    responsible_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("cycle_id", "unit_id", name="uq_cycle_units"),
        Index("ix_cycle_units_cycle_id", "cycle_id"),
        Index("ix_cycle_units_unit_id", "unit_id"),
    )

    cycle: Mapped["PlanningCycle"] = relationship("PlanningCycle", back_populates="units")
    unit: Mapped["Unit"] = relationship("Unit", back_populates="memberships")


class Resource(Base):
    """A canonical, organization-wide resource (room or instructor).

    ``kind`` distinguishes 'room' vs 'instructor'. Each unit references the
    SAME row — it never duplicates a resource.
    """

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # room|instructor
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    # Logical-delete timestamp (NULL = active). Soft-delete preserves audit history.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "kind", "name", name="uq_resources_org_kind_name"),
        CheckConstraint(
            "kind <> 'room' OR capacity IS NULL OR capacity > 0",
            name="ck_resources_room_capacity_positive",
        ),
        Index("ix_resources_organization_id", "organization_id"),
    )

    availability: Mapped[list["ResourceAvailability"]] = relationship(
        "ResourceAvailability", back_populates="resource", cascade="all, delete-orphan"
    )
    commitments: Mapped[list["ResourceCommitment"]] = relationship(
        "ResourceCommitment", back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceAvailability(Base):
    """Availability window for a resource within a specific PlanningCycle.

    Stored as (weekday, start/end HH:MM). Missing windows mean "unknown",
    NOT "free" (06). Availability is per-cycle, never global.
    """

    __tablename__ = "resource_availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    # 0=Saturday ... 6=Friday (Q9 convention: 0=شنبه … 6=جمعه)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    end_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)
    # Logical-delete timestamp (NULL = active). Soft-delete preserves audit history.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "resource_id", "cycle_id", "weekday", "start_hhmm", "end_hhmm",
            name="uq_resource_availability",
        ),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"),
        Index("ix_resource_availability_resource_id", "resource_id"),
        Index("ix_resource_availability_cycle_id", "cycle_id"),
    )

    resource: Mapped["Resource"] = relationship("Resource", back_populates="availability")


class ResourceCommitment(Base):
    """A binding commitment of a resource in a cycle (solver input, Phase 4)."""

    __tablename__ = "resource_commitments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)
    end_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_commitment_weekday"),
        Index("ix_resource_commitments_resource_id", "resource_id"),
        Index("ix_resource_commitments_cycle_id", "cycle_id"),
    )

    resource: Mapped["Resource"] = relationship("Resource", back_populates="commitments")


class Cohort(Base):
    """A stable target group / entry (e.g. an intake year) of a Unit."""

    __tablename__ = "cohorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("unit_id", "name", name="uq_cohorts_unit_name"),
        Index("ix_cohorts_unit_id", "unit_id"),
        Index("ix_cohorts_organization_id", "organization_id"),
    )

    cycle_links: Mapped[list["CycleCohort"]] = relationship(
        "CycleCohort", back_populates="cohort", cascade="all, delete-orphan"
    )


class CycleCohort(Base):
    """Per-PlanningCycle expected enrollment for a Cohort (05: don't duplicate)."""

    __tablename__ = "cycle_cohorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    cohort_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False
    )
    expected_enrollment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("cycle_id", "cohort_id", name="uq_cycle_cohorts"),
        CheckConstraint("expected_enrollment >= 0", name="ck_cycle_cohorts_enrollment_nonneg"),
        Index("ix_cycle_cohorts_cycle_id", "cycle_id"),
        Index("ix_cycle_cohorts_cohort_id", "cohort_id"),
    )

    cycle: Mapped["PlanningCycle"] = relationship("PlanningCycle")
    cohort: Mapped["Cohort"] = relationship("Cohort", back_populates="cycle_links")


class Course(Base):
    """Organization-wide course catalog entry (stable identity)."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_courses_org_code"),
        Index("ix_courses_organization_id", "organization_id"),
    )

    offerings: Mapped[list["CourseOffering"]] = relationship(
        "CourseOffering", back_populates="course", cascade="all, delete-orphan"
    )


class CourseOffering(Base):
    """A course/activity scheduled within a PlanningCycle.

    Can serve multiple Units and Cohorts via join tables; a shared offering
    keeps a single canonical MeetingRequirement.
    """

    __tablename__ = "course_offerings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    planning_cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meetings_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    required_room_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    room_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "planning_cycle_id", "course_id", "section",
            name="uq_offerings_cycle_course_section",
        ),
        CheckConstraint("meetings_per_week > 0", name="ck_offerings_meetings_positive"),
        CheckConstraint("duration_minutes > 0", name="ck_offerings_duration_positive"),
        Index("ix_offerings_course_id", "course_id"),
        Index("ix_offerings_planning_cycle_id", "planning_cycle_id"),
    )

    course: Mapped["Course"] = relationship("Course", back_populates="offerings")
    planning_cycle: Mapped["PlanningCycle"] = relationship("PlanningCycle", back_populates="courses")
    participants: Mapped[list["OfferingUnit"]] = relationship(
        "OfferingUnit", back_populates="offering", cascade="all, delete-orphan"
    )
    target_cohorts: Mapped[list["OfferingCohort"]] = relationship(
        "OfferingCohort", back_populates="offering", cascade="all, delete-orphan"
    )
    meeting_requirement: Mapped[Optional["MeetingRequirement"]] = relationship(
        "MeetingRequirement",
        back_populates="offering",
        cascade="all, delete-orphan",
        uselist=False,
    )


class OfferingUnit(Base):
    """Join: which Units participate in / own the offering's input."""

    __tablename__ = "offering_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    # unit-level expected enrollment contribution for this offering
    expected_enrollment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 06 shared-offering flow: when this unit proposes the shared offering,
    # the manager must nominate the canonical resources for it (Q12).
    # All connected units see the same Resource IDs — a shared offering never
    # duplicates a resource per unit.
    room_resource_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("resources.id", ondelete="SET NULL"), nullable=True
    )
    instructor_resource_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("resources.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("offering_id", "unit_id", name="uq_offering_units"),
        CheckConstraint("expected_enrollment >= 0", name="ck_offering_units_enrollment_nonneg"),
        Index("ix_offering_units_offering_id", "offering_id"),
        Index("ix_offering_units_unit_id", "unit_id"),
        CheckConstraint(
            "room_resource_id IS NULL OR instructor_resource_id IS NULL "
            "OR room_resource_id <> instructor_resource_id",
            name="ck_offering_units_resources_distinct",
        ),
        Index("ix_offering_units_room_resource", "room_resource_id"),
        Index("ix_offering_units_instructor_resource", "instructor_resource_id"),
    )

    offering: Mapped["CourseOffering"] = relationship(
        "CourseOffering", back_populates="participants"
    )
    unit: Mapped["Unit"] = relationship("Unit")


class OfferingCohort(Base):
    """Join: which Cohorts the offering targets (enrollment per cohort)."""

    __tablename__ = "offering_cohorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    cohort_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cohorts.id", ondelete="CASCADE"), nullable=False
    )
    expected_enrollment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("offering_id", "cohort_id", name="uq_offering_cohorts"),
        CheckConstraint("expected_enrollment >= 0", name="ck_offering_cohorts_enrollment_nonneg"),
        Index("ix_offering_cohorts_offering_id", "offering_id"),
        Index("ix_offering_cohorts_cohort_id", "cohort_id"),
    )

    offering: Mapped["CourseOffering"] = relationship(
        "CourseOffering", back_populates="target_cohorts"
    )
    cohort: Mapped["Cohort"] = relationship("Cohort")


class MeetingRequirement(Base):
    """The single canonical meeting requirement for (shared) offerings.

    Shared offerings must NOT spawn multiple requirements — one row per
    offering; the solver builds shared slots once.
    """

    __tablename__ = "meeting_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    allowed_weekday_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allowed_weekday_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_window_hhmm: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    end_window_hhmm: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "allowed_weekday_min IS NULL OR allowed_weekday_max IS NULL "
            "OR allowed_weekday_min <= allowed_weekday_max",
            name="ck_meeting_req_weekday_range",
        ),
        Index("ix_meeting_requirements_offering_id", "offering_id"),
    )

    offering: Mapped["CourseOffering"] = relationship(
        "CourseOffering", back_populates="meeting_requirement"
    )