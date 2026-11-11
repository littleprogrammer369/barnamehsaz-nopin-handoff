"""Phase 3 domain model: submissions, revisions, wizard drafts, shared-offering
approvals, and a domain-level audit trail.

Design (05 / 06 / 08):
- Submission is per (PlanningCycle, Unit); only one active submission row.
- SubmissionRevision is append-only: each submit/resubmit creates a new row
  with a serialized input snapshot; prior revisions are never mutated.
- WizardDraft holds mutable section-by-section progress for save/resume.
- SharedOfferingApproval is one row per (offering, unit) so every participating
  unit records an explicit approval (06 shared-offering flow, no auto-merge).
- DomainAuditEvent is an append-only trail of domain actions (who/what/when).
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Status constants (kept in Python as the source of truth for transitions).
SUB_DRAFT = "draft"
SUB_SUBMITTED = "submitted"
SUB_NEEDS_CHANGES = "needs_changes"
SUB_APPROVED = "approved"

APPROVAL_PENDING = "pending"
APPROVAL_UNIT_APPROVED = "unit_approved"
APPROVAL_NEEDS_CHANGES = "needs_changes"

OFFERING_DRAFT = "draft"
OFFERING_AWAITING = "awaiting_review"
OFFERING_APPROVED = "approved"
OFFERING_NEEDS_CHANGES = "needs_changes"


class Submission(Base):
    """The active planning submission for one Unit within one PlanningCycle.

    ``version`` is an optimistic-concurrency counter; a stale ``expected_version``
    on a state transition yields 409 (10) instead of a silent overwrite.
    """

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SUB_DRAFT)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # When True the unit's input is locked until a manager returns it for changes
    # or the manager explicitly reopens it (06: no silent edit of a submitted
    # version).
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("cycle_id", "unit_id", name="uq_submissions_cycle_unit"),
        Index("ix_submissions_cycle_id", "cycle_id"),
        Index("ix_submissions_unit_id", "unit_id"),
        Index("ix_submissions_organization_id", "organization_id"),
        CheckConstraint(
            "status IN ('draft','submitted','needs_changes','approved')",
            name="ck_submissions_status",
        ),
    )

    revisions: Mapped[list["SubmissionRevision"]] = relationship(
        "SubmissionRevision", back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionRevision(Base):
    """Append-only revision of a Submission. Never mutated; new rows instead."""

    __tablename__ = "submission_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # Serialized, immutable snapshot of the submitted input state.
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("submission_id", "revision_no", name="uq_submission_revisions_no"),
        Index("ix_submission_revisions_submission_id", "submission_id"),
        Index("ix_submission_revisions_created_by", "created_by_user_id"),
    )

    submission: Mapped["Submission"] = relationship(
        "Submission", back_populates="revisions"
    )


class WizardDraft(Base):
    """Mutable, per (cycle, unit) wizard progress for save/resume.

    Distinct from SubmissionRevision: this is working state and may be updated
    freely until the submission is locked. ``section_state`` is a free-form
    JSON object keyed by wizard section.
    """

    __tablename__ = "wizard_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    section_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("cycle_id", "unit_id", name="uq_wizard_drafts_cycle_unit"),
        Index("ix_wizard_drafts_cycle_id", "cycle_id"),
        Index("ix_wizard_drafts_unit_id", "unit_id"),
    )


class SharedOfferingApproval(Base):
    """Explicit per-unit approval for a (potentially shared) offering.

    One row per (offering, unit). A shared offering cannot be solved/published
    until every participating unit has recorded UNIT_APPROVED and the manager
    finalizes it (06 shared-offering flow)."""

    __tablename__ = "shared_offering_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=APPROVAL_PENDING)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 06 shared-offering flow step 6: after-approval data changes do not
    # delete approval history — they mark the affected approvals stale so
    # the units can explicitly re-confirm.
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    stale_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("offering_id", "unit_id", name="uq_shared_approvals_offering_unit"),
        Index("ix_shared_approvals_offering_id", "offering_id"),
        Index("ix_shared_approvals_unit_id", "unit_id"),
        CheckConstraint(
            "status IN ('pending','unit_approved','needs_changes')",
            name="ck_shared_approvals_status",
        ),
    )


class DomainAuditEvent(Base):
    """Append-only domain audit trail (submit/return/approve/preflight/...).

    Distinct from the security ``audit_events`` table (base.py). No update or
    delete API is exposed; history is preserved."""

    __tablename__ = "domain_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    subject_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_domain_audit_events_org_id", "organization_id"),
        Index("ix_domain_audit_events_subject", "subject_type", "subject_id"),
    )


class SubmissionComment(Base):
    """Append-only free-text comment attached to a Submission or a specific
    SubmissionRevision. Does not affect lifecycle state; purely annotation.

    06/08 spec: comments/annotations must be tracked alongside submissions
    and revisions; they are immutable once written.
    """

    __tablename__ = "submission_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    # When target == 'revision', this points to the specific revision number.
    revision_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_submission_comments_submission_id", "submission_id"),
        Index("ix_submission_comments_restriction", "submission_id", "revision_no"),
    )

    submission: Mapped["Submission"] = relationship("Submission")
