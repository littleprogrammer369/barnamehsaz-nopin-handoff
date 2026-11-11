"""Phase 4 domain model: solver runs, corrections, stale-ing.

Design (05 / 07):
- SolverRun is per PlanningCycle; each run captures an immutable
  input_snapshot (all offerings, meeting requirements, resources,
  availability, commitments) so historical runs are never mutated.
- SolverAssignment rows are appended once per feasible run and never
  updated or deleted — they represent the solver's proposed schedule.
- OfferingCorrection is the append-only track for manager manual
  corrections: actor, reason, and before/after values are recorded
  without rewriting the unit's original data.
- When a correction (or any data change after approval) affects data
  that approvals cover, all existing unit approvals for the offering
  are marked stale (status → 'pending') and a stale marker row is
  written. History is preserved, not deleted.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# SolverRun statuses (07):
RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_FEASIBLE = "feasible"
RUN_INFEASIBLE = "infeasible"
RUN_FAILED = "failed"

# Status constant for the stale-ing mechanism
APPROVAL_STALE = "stale"


class SolverRun(Base):
    """One solver execution for a PlanningCycle.

    ``input_snapshot`` is an immutable JSON blob of all data the solver
    read at run-time.  ``result_snapshot`` holds the solver output
    (assignments, objective score, warnings, or infeasibility causes)
    and is written exactly once when the run reaches a terminal state.

    ``stale`` is True when a data-level change (correction, re-submission,
    new meeting requirement, ...) has affected inputs this run read.
    Stale runs remain in history for comparison; they must not be used
    to publish a final schedule.
    """

    __tablename__ = "solver_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    # queued → running → feasible | infeasible | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RUN_QUEUED)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    objective_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    # Immutable snapshot of all input data at run time (07 hard constraint #11)
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Terminal-state result: assignments, soft warnings, or infeasible causes
    result_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','feasible','infeasible','failed')",
            name="ck_solver_runs_status",
        ),
        Index("ix_solver_runs_cycle_id", "cycle_id"),
        Index("ix_solver_runs_org_id", "organization_id"),
    )
class SolverAssignment(Base):
    """One concrete slot assignment proposed by a feasible SolverRun.

    A shared offering produces exactly ONE assignment row (07 hard #9);
    all connected units/cohorts see the same meeting.

    Row is append-only: once a run reaches 'feasible', its assignments
    are never modified.  Manual edits by admin create a NEW run, not an
    edit of this table.
    """

    __tablename__ = "solver_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("solver_runs.id", ondelete="CASCADE"), nullable=False
    )
    offering_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    # Chosen resource for this slot
    resource_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("resources.id"), nullable=True
    )
    # 07 hard #8/#9: occurrence number of this assignment within the run
    occurrence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # The chosen weekday and slot (from the meeting requirement window)
    weekday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_hhmm: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    end_hhmm: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    # 07 hard #8: occurrences count and duration are recorded here so a
    # publish step can validate without re-reading mutable offering data.
    meetings_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("run_id", "offering_id", "occurrence_no",
                         "resource_id",
                         name="uq_solver_assignments_run_offering_occurrence"),
        Index("ix_solver_assignments_run_id", "run_id"),
        Index("ix_solver_assignments_offering_id", "offering_id"),
    )


class OfferingCorrection(Base):
    """Append-only manager correction for an offering (06 shared-offering
    flow step 4; 05 'نسخهٔ دادهٔ واحد vs نسخهٔ اصلاح مدیریتی قابل‌ردیابی').

    - The unit's original submission data is never rewritten.
    - Each correction is a new row with actor_user_id + reason +
      before/after values.
    - If the corrected field affects approval-impacting data, all
      existing unit approvals for the offering are marked 'stale'
      (status → 'stale') so they must be explicitly re-confirmed.
    """

    __tablename__ = "offering_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    # Which field was corrected, e.g. 'expected_enrollment', 'duration_minutes'
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    before_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # True when this correction invalidated existing approvals
    approvals_marked_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_offering_corrections_offering_id", "offering_id"),
        Index("ix_offering_corrections_cycle_id", "cycle_id"),
        Index("ix_offering_corrections_org_id", "organization_id"),
    )



# ----------------------------------------------------------------------
# PublishedSchedule (08): immutable, versioned, auditable published
# schedule. Written once after explicit manager confirmation; never
# overwritten, never deleted — history is preserved for compare/retry.
# ----------------------------------------------------------------------

PUBLISHED_STATUS_DRAFT = "draft"
PUBLISHED_STATUS_CURRENT = "current"
PUBLISHED_STATUS_PREVIOUS = "previous"
PUBLISHED_STATUS_STALE = "stale"


class PublishedSchedule(Base):
    """One immutable published version of a PlanningCycle's final schedule.

    Each row records a *version* of the published schedule: who
    published it, which run it came from, which Cycle/Unit it covers,
    and its current/past relationship to other versions. Because the
    schedule body itself lives on immutable rows (SolverAssignment),
    the PublishedSchedule row is a lightweight envelope that can be
    versioned independently.

    Status lifecycle (08):
      draft    -> manager has created the published version but not
                 yet confirmed publication (feature-flag ready).
      current  -> the live version used by the UI for read/export.
      previous -> superseded by a newer version; kept for compare and
                  download.
      stale    -> the published version is no longer valid (inputs
                  changed after publication), marked stale until
                  republished.
    """

    __tablename__ = "published_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("solver_runs.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    # New version identifier (floats allow fractional patches; never
    # reused a value that a previous version had — 08 preserves history).
    version: Mapped[float] = mapped_column(Integer, nullable=False)
    # Status (08): draft | current | previous | stale
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PUBLISHED_STATUS_DRAFT
    )
    # Immutable run snapshot from the point of publication
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Which solver run produced this published version
    source_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("solver_runs.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # Audit trail for the publish admin action
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # True when data changes invalidate this published version
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','current','previous','stale')",
            name="ck_published_schedules_status",
        ),
        Index("ix_published_schedules_run_id", "run_id"),
        Index("ix_published_schedules_cycle_id", "cycle_id"),
        Index("ix_published_schedules_org_id", "organization_id"),
        Index(
            "ix_published_schedules_status",
            "organization_id",
            "status",
            "cycle_id",
        ),
    )
