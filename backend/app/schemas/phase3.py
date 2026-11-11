"""Pydantic v2 create/read schemas for Phase 3 domain objects."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ---------------- Submission ----------------
class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cycle_id: int
    unit_id: int
    organization_id: int
    status: str
    version: int
    locked: bool


class SubmissionRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    submission_id: int
    revision_no: int
    input_snapshot: Optional[Dict[str, Any]]
    created_by_user_id: Optional[int]


class SubmitActionRequest(BaseModel):
    """Body for submit / resubmit action on an existing submission."""
    input_snapshot: Optional[Dict[str, Any]] = None
    expected_version: int = 0


class CreateSubmissionRequest(BaseModel):
    """Body for creating a new submission (draft)."""
    cycle_id: int
    unit_id: int
    input_snapshot: Optional[Dict[str, Any]] = None
    expected_version: int = 0


class SubmitStateRequest(BaseModel):
    expected_version: int = 0
    input_snapshot: Optional[Dict[str, Any]] = None


class NeedsChangesRequest(BaseModel):
    reason: str = Field(min_length=3)
    comment: Optional[str] = None
    expected_version: int = 0


class ApproveSubmissionRequest(BaseModel):
    comment: Optional[str] = None
    expected_version: int = 0


class ResubmitRequest(BaseModel):
    input_snapshot: Optional[Dict[str, Any]] = None
    expected_version: int = 0


# ---------------- Wizard ----------------
class WizardDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cycle_id: int
    unit_id: int
    section_state: Dict[str, Any]
    completed: bool


class WizardDraftUpsertRequest(BaseModel):
    cycle_id: int
    unit_id: int
    section_state: Optional[Dict[str, Any]] = None
    completed: Optional[bool] = None


# ---------------- Shared offering approvals ----------------
class SharedOfferingApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    offering_id: int
    unit_id: int
    status: str
    comment: Optional[str]
    decided_by_user_id: Optional[int]


class RecordSharedApprovalRequest(BaseModel):
    """Called by a participating unit's manager to record their approval.

    ``unit_id`` is mandatory: the recording unit explicitly identifies which
    unit's approval it is recording (06 shared-offering flow — no implicit
    default to the first participating unit)."""
    status: str = Field(description="unit_approved | needs_changes")
    unit_id: int
    comment: Optional[str] = None


# ---------------- Preflight ----------------
class PreflightBlocker(BaseModel):
    code: str
    message: str
    subject_type: Optional[str] = None
    subject_id: Optional[int] = None


class PreflightResult(BaseModel):
    can_submit: bool
    blockers: List[PreflightBlocker]
    warnings: List[PreflightBlocker]


# ---------------- Comment / annotation ----------------
class CommentSubmissionRequest(BaseModel):
    """Attach a free-text comment to a submission or a specific revision.

    ``target`` is either 'submission' (when ``revision_no`` is omitted) or
    'revision' (when ``revision_no`` is provided). Comments are append-only
    and audited; they do not modify the submission lifecycle state.
    """
    text: str = Field(min_length=2, max_length=2000)
    target: str = Field(default="submission", pattern="^(submission|revision)$")
    revision_no: Optional[int] = None


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    submission_id: int
    revision_no: Optional[int]
    actor_user_id: Optional[int]
    text: str
    created_at: Optional[datetime]
class DomainAuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    organization_id: Optional[int]
    actor_user_id: Optional[int]
    subject_type: Optional[str]
    subject_id: Optional[int]
    detail: Optional[Dict[str, Any]]
    created_at: Optional[datetime]


class SharedFinalizeRequest(BaseModel):
    """Admin decision to finalize or return a shared offering."""
    decision: str = Field(description="'approve' or 'return'")
    reason: Optional[str] = None
