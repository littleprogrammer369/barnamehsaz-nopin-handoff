"""Phase 3 routers: submissions lifecycle, step-wizard state, shared-offering
approval flow, global preflight checks, version history and append-only audit.

All endpoints are auth-gated and org-scoped via the caller's membership. Write
state transitions are gated by admin or unit_manager; manager-only decisions
(needs_changes / shared-finalize) additionally require the admin role.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.base import User, Membership
from app.models.phase2 import (
    PlanningCycle, Unit, Course, CourseOffering, OfferingUnit,
    OfferingCohort, MeetingRequirement, ResourceAvailability, CycleUnit,
)
from app.models.phase3 import (
    Submission, SubmissionRevision, SubmissionComment,
    WizardDraft, SharedOfferingApproval, DomainAuditEvent,
    SUB_DRAFT, SUB_SUBMITTED, SUB_NEEDS_CHANGES, SUB_APPROVED,
    APPROVAL_PENDING, APPROVAL_UNIT_APPROVED, APPROVAL_NEEDS_CHANGES,
)
from app.routers.phase2 import get_current_user, require_password_changed
from app.services.submission_tracking import get_submission_status
from app.core.rbac import apply_unit_filter, get_unit_for_user, ROLE_UNIT_MANAGER
from app.schemas.phase3 import (
    SubmissionRead, SubmissionRevisionRead, SubmitActionRequest, CreateSubmissionRequest,
    NeedsChangesRequest, ApproveSubmissionRequest, ResubmitRequest,
    WizardDraftRead, WizardDraftUpsertRequest,
    SharedOfferingApprovalRead, RecordSharedApprovalRequest,
    PreflightBlocker, PreflightResult, DomainAuditEventRead,
    SharedFinalizeRequest,
    CommentSubmissionRequest, CommentRead,
)

router = APIRouter(prefix="/phase3", tags=["phase3"])


def _org_id_for(user: User, db: Session) -> int:
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if membership is None:
        raise HTTPException(status_code=403, detail="User has no organization membership")
    return membership.organization_id


def _require_role(user: User, db: Session, roles: list) -> None:
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.role.in_(roles))
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail=f"{'/'.join(roles)} role required")


def _audit(db: Session, action: str, org_id: int, actor_user_id: int,
           subject_type: str, subject_id: Optional[int], detail: Optional[dict] = None):
    db.add(DomainAuditEvent(
        action=action, organization_id=org_id, actor_user_id=actor_user_id,
        subject_type=subject_type, subject_id=subject_id, detail=detail,
    ))


def _check_version(submission: Submission, expected_version: int) -> None:
    if expected_version != submission.version:
        raise HTTPException(
            status_code=409,
            detail=f"Stale version: server is at {submission.version}, got {expected_version}",
        )


def _bump_revision(db: Session, submission: Submission, actor_user_id: int,
                   snapshot: Optional[dict]) -> SubmissionRevision:
    latest = (
        db.query(SubmissionRevision)
        .filter(SubmissionRevision.submission_id == submission.id)
        .order_by(SubmissionRevision.revision_no.desc())
        .first()
    )
    rev_no = (latest.revision_no + 1) if latest else 1
    revision = SubmissionRevision(
        submission_id=submission.id, revision_no=rev_no,
        input_snapshot=snapshot, created_by_user_id=actor_user_id,
    )
    db.add(revision)
    return revision


# ------------------------------------------------------------------ submissions
@router.get("/submissions", response_model=List[SubmissionRead])
def list_submissions(
    cycle_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List submissions with unit isolation for unit_managers.
    
    Unit managers see only their own unit's submissions.
    Admins see all submissions.
    """
    org_id = _org_id_for(current_user, db)
    q = db.query(Submission).filter(Submission.organization_id == org_id)
    
    # Apply unit filtering based on user role
    q = apply_unit_filter(current_user, db, org_id, q, Submission.unit_id)
    
    if cycle_id is not None:
        q = q.filter(Submission.cycle_id == cycle_id)
    if unit_id is not None:
        q = q.filter(Submission.unit_id == unit_id)
    return q.all()


@router.get("/cycles/{cycle_id}/submission-status")
def get_cycle_submission_status(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get submission progress for a planning cycle (0/5 to 5/5).
    
    Returns:
    {
        "total_units": 5,
        "submitted_count": N,
        "approved_count": M,
        "can_preflight": bool,
        "can_publish": bool
    }
    """
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id,
        PlanningCycle.organization_id == org_id,
        PlanningCycle.deleted_at.is_(None),
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    
    return get_submission_status(cycle_id, db)


@router.post("/submissions", response_model=SubmissionRead, status_code=201)
def create_submission(
    body: CreateSubmissionRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin", "unit_manager"])
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == body.cycle_id, PlanningCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found in this organization")
    unit = db.query(Unit).filter(Unit.id == body.unit_id, Unit.organization_id == org_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found in this organization")
    existing = db.query(Submission).filter(
        Submission.cycle_id == body.cycle_id, Submission.unit_id == body.unit_id).first()
    if existing:
        _check_version(existing, body.expected_version)
        if body.input_snapshot is not None:
            _bump_revision(db, existing, current_user.id, body.input_snapshot)
        existing.version += 1
        db.commit()
        db.refresh(existing)
        _audit(db, "submission_update", org_id, current_user.id, "submission", existing.id,
               {"version": existing.version})
        db.commit()
        return existing
    sub = Submission(cycle_id=body.cycle_id, unit_id=body.unit_id, organization_id=org_id,
                     status=SUB_DRAFT, version=0, locked=False)
    db.add(sub)
    db.flush()
    if body.input_snapshot is not None:
        _bump_revision(db, sub, current_user.id, body.input_snapshot)
    db.commit()
    db.refresh(sub)
    _audit(db, "submission_create", org_id, current_user.id, "submission", sub.id)
    db.commit()
    return sub


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get submission detail with unit isolation.
    
    Unit managers can only view their own unit's submissions.
    Admins can view any submission.
    """
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check unit access
    user_unit_id = get_unit_for_user(current_user.id, org_id, db)
    if user_unit_id is not None and sub.unit_id != user_unit_id:
        # Unit manager trying to access other unit's submission
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view submissions for your assigned unit"
        )
    
    return sub


# ------------------------------------------------------------------ lifecycle
@router.post("/submissions/{submission_id}/submit", response_model=SubmissionRead)
def submit(
    submission_id: int,
    body: SubmitActionRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin", "unit_manager"])
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status not in (SUB_DRAFT, SUB_NEEDS_CHANGES):
        raise HTTPException(status_code=409, detail=f"Cannot submit from status {sub.status}")
    _check_version(sub, body.expected_version)
    _bump_revision(db, sub, current_user.id, body.input_snapshot)
    sub.status = SUB_SUBMITTED
    sub.locked = True
    sub.version += 1
    db.flush()
    _audit(db, "submit", org_id, current_user.id, "submission", sub.id, {"version": sub.version})
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/submissions/{submission_id}/needs-changes", response_model=SubmissionRead)
def request_changes(
    submission_id: int,
    body: NeedsChangesRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin"])
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != SUB_SUBMITTED:
        raise HTTPException(status_code=409, detail=f"Cannot return from status {sub.status}")
    _check_version(sub, body.expected_version)
    sub.status = SUB_NEEDS_CHANGES
    sub.locked = False
    sub.version += 1
    db.flush()
    _audit(db, "request_changes", org_id, current_user.id, "submission", sub.id,
           {"reason": body.reason, "comment": body.comment, "version": sub.version})
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/submissions/{submission_id}/approve", response_model=SubmissionRead)
def approve(
    submission_id: int,
    body: ApproveSubmissionRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin"])
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status != SUB_SUBMITTED:
        raise HTTPException(status_code=409, detail=f"Cannot approve from status {sub.status}")
    _check_version(sub, body.expected_version)
    sub.status = SUB_APPROVED
    sub.version += 1
    db.flush()
    _audit(db, "approve", org_id, current_user.id, "submission", sub.id,
           {"comment": body.comment, "version": sub.version})
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/submissions/{submission_id}/revisions", response_model=List[SubmissionRevisionRead])
def list_revisions(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return (
        db.query(SubmissionRevision)
        .filter(SubmissionRevision.submission_id == submission_id)
        .order_by(SubmissionRevision.revision_no)
        .all()
    )


# ------------------------------------------------------------------ comments
@router.post("/submissions/{submission_id}/comments",
             response_model=CommentRead, status_code=201)
def add_comment(
    submission_id: int,
    body: CommentSubmissionRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Append a free-text comment to a submission or a specific revision.

    Requires admin or unit_manager; comment is append-only (no update/delete).
    """
    _require_role(current_user, db, ["admin", "unit_manager"])
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if body.target == "revision" and body.revision_no is None:
        raise HTTPException(
            status_code=400,
            detail="revision_no is required when target='revision'")
    comment = SubmissionComment(
        submission_id=submission_id,
        revision_no=body.revision_no if body.target == "revision" else None,
        actor_user_id=current_user.id,
        text=body.text,
    )
    db.add(comment)
    db.flush()
    _audit(db, "comment_add", org_id, current_user.id, "submission", submission_id,
           {"target": body.target, "revision_no": body.revision_no})
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/submissions/{submission_id}/comments",
            response_model=List[CommentRead])
def list_comments(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    sub = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.organization_id == org_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return (
        db.query(SubmissionComment)
        .filter(SubmissionComment.submission_id == submission_id)
        .order_by(SubmissionComment.id)
        .all()
    )


# ------------------------------------------------------------------ wizard
@router.post("/wizard-state", response_model=WizardDraftRead)
def upsert_wizard(
    body: WizardDraftUpsertRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin", "unit_manager"])
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == body.cycle_id, PlanningCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found in this organization")
    draft = db.query(WizardDraft).filter(
        WizardDraft.cycle_id == body.cycle_id, WizardDraft.unit_id == body.unit_id).first()
    if draft is None:
        draft = WizardDraft(cycle_id=body.cycle_id, unit_id=body.unit_id, section_state={}, completed=False)
        db.add(draft)
    if body.section_state is not None:
        draft.section_state = body.section_state
    if body.completed is not None:
        draft.completed = body.completed
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/wizard-state", response_model=Optional[WizardDraftRead])
def get_wizard(
    cycle_id: int,
    unit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id, PlanningCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found in this organization")
    return db.query(WizardDraft).filter(
        WizardDraft.cycle_id == cycle_id, WizardDraft.unit_id == unit_id).first()


# ------------------------------------------------------------------ shared-offering approval flow
def _assert_offering_in_org(offering: CourseOffering, org_id: int, db: Session) -> None:
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id,
        PlanningCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=403, detail="Offering does not belong to this organization")


@router.post("/offerings/{offering_id}/shared-approvals",
             response_model=SharedOfferingApprovalRead, status_code=201)
def record_shared_approval(
    offering_id: int,
    body: RecordSharedApprovalRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin", "unit_manager"])
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    _assert_offering_in_org(offering, org_id, db)
    if body.status not in (APPROVAL_UNIT_APPROVED, APPROVAL_NEEDS_CHANGES):
        raise HTTPException(status_code=400, detail="status must be 'unit_approved' or 'needs_changes'")
    # 06 shared-offering rule: unit_id is required — no implicit default.
    unit_id = body.unit_id
    if unit_id is None:
        raise HTTPException(status_code=400, detail="unit_id is required (explicit, no implicit default)")
    # The unit must participate in this offering.
    offering_units = db.query(OfferingUnit).filter(OfferingUnit.offering_id == offering_id).all()
    if not any(ou.unit_id == unit_id for ou in offering_units):
        raise HTTPException(status_code=403, detail=f"Unit {unit_id} does not participate in this offering")
    # Permission: a unit_manager may only record approval for their own unit.
    # Admin may record for any participating unit in the organization.
    is_admin = db.query(Membership).filter(
        Membership.user_id == current_user.id,
        Membership.organization_id == org_id,
        Membership.role == "admin",
    ).first() is not None
    if not is_admin:
        # unit_manager: only allowed for units they own/created a submission for.
        my_sub = db.query(Submission).filter(
            Submission.unit_id == unit_id,
            Submission.cycle_id == offering.planning_cycle_id,
            Submission.organization_id == org_id,
        ).order_by(Submission.version.desc()).first()
        if my_sub is None or my_sub.version == 0:
            # No submission yet for this unit in this cycle: only admin can
            # set an approval before the unit has submitted its data.
            raise HTTPException(
                status_code=403,
                detail="Unit manager may only record approval for their own unit after it has submitted data",
            )
    approval = db.query(SharedOfferingApproval).filter(
        SharedOfferingApproval.offering_id == offering_id,
        SharedOfferingApproval.unit_id == unit_id).first()
    if approval is None:
        approval = SharedOfferingApproval(offering_id=offering_id, unit_id=unit_id)
        db.add(approval)
    approval.status = body.status
    approval.comment = body.comment
    approval.decided_by_user_id = current_user.id
    db.flush()
    _audit(db, "shared_approval", org_id, current_user.id, "offering", offering_id,
           {"unit_id": unit_id, "status": body.status})
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/offerings/{offering_id}/shared-approvals",
            response_model=List[SharedOfferingApprovalRead])
def list_shared_approvals(
    offering_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    _assert_offering_in_org(offering, org_id, db)
    return (
        db.query(SharedOfferingApproval)
        .filter(SharedOfferingApproval.offering_id == offering_id)
        .order_by(SharedOfferingApproval.unit_id)
        .all()
    )


@router.post("/offerings/{offering_id}/shared-finalize")
def shared_finalize(
    offering_id: int,
    body: SharedFinalizeRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_role(current_user, db, ["admin"])
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    _assert_offering_in_org(offering, org_id, db)
    if body.decision not in ("approve", "return"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'return'")

    participating = db.query(OfferingUnit).filter(OfferingUnit.offering_id == offering_id).all()
    approvals = {
        a.unit_id: a.status
        for a in db.query(SharedOfferingApproval)
        .filter(SharedOfferingApproval.offering_id == offering_id).all()
    }

    if body.decision == "approve":
        missing = [p.unit_id for p in participating
                   if approvals.get(p.unit_id) != APPROVAL_UNIT_APPROVED]
        if missing:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot finalize: units {missing} have not recorded 'unit_approved'",
            )
        outcome = "approved"
        _audit(db, "shared_approve", org_id, current_user.id, "offering", offering_id,
               {"approved_units": list(approvals.keys())})
        db.commit()
        return {"offering_id": offering_id, "outcome": outcome, "re_pend_approvals": False}

    # 'return': any change after a prior approval re-pends all approvals (no auto-merge).
    for a in db.query(SharedOfferingApproval).filter(
        SharedOfferingApproval.offering_id == offering_id).all():
        if a.status == APPROVAL_UNIT_APPROVED:
            a.status = APPROVAL_PENDING
            a.decided_by_user_id = None
    _audit(db, "shared_return", org_id, current_user.id, "offering", offering_id,
           {"reason": body.reason})
    db.commit()
    return {"offering_id": offering_id, "outcome": "needs_changes", "re_pend_approvals": True}


# ------------------------------------------------------------------ preflight
@router.get("/preflight", response_model=PreflightResult)
def preflight(
    cycle_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run preflight checks on planning cycle(s).
    
    Requires: All units in the cycle must have submitted before preflight can run.
    """
    org_id = _org_id_for(current_user, db)
    q = db.query(PlanningCycle).filter(PlanningCycle.organization_id == org_id)
    if cycle_id is not None:
        q = q.filter(PlanningCycle.id == cycle_id)
    cycles = q.all()
    
    # GATE: Check cycle-specific unit submission requirement
    for cycle in cycles:
        status = get_submission_status(cycle.id, db)
        total_units = status["total_units"]
        submitted_count = status["submitted_count"]
        if submitted_count < total_units:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Preflight requires all {total_units} units to be submitted. Currently {submitted_count}/{total_units} units have submitted."
            )
    
    blockers: List[PreflightBlocker] = []
    warnings: List[PreflightBlocker] = []

    for cycle in cycles:
        offerings = db.query(CourseOffering).filter(
            CourseOffering.planning_cycle_id == cycle.id).all()
        for offering in offerings:
            participants = db.query(OfferingUnit).filter(
                OfferingUnit.offering_id == offering.id).all()

            # Shared offerings (more than one participating unit) require
            # explicit unit approvals from every participant.
            if len(participants) > 1:
                approvals = {
                    a.unit_id: a.status
                    for a in db.query(SharedOfferingApproval)
                    .filter(SharedOfferingApproval.offering_id == offering.id).all()
                }
                missing = [p.unit_id for p in participants
                           if approvals.get(p.unit_id) != APPROVAL_UNIT_APPROVED]
                if missing:
                    blockers.append(PreflightBlocker(
                        code="SHARED_OFFERING_UNAPPROVED",
                        message=f"Shared offering {offering.id} lacks approvals from units {missing}",
                        subject_type="offering", subject_id=offering.id,
                    ))

            # At most one meeting requirement per offering.
            mr_count = db.query(MeetingRequirement).filter(
                MeetingRequirement.offering_id == offering.id).count()
            if mr_count > 1:
                blockers.append(PreflightBlocker(
                    code="DUPLICATE_MEETING_REQUIREMENT",
                    message=f"Offering {offering.id} has {mr_count} meeting requirements (max 1)",
                    subject_type="offering", subject_id=offering.id,
                ))

            # Enrollment must not exceed required room capacity when set.
            total_enrollment = sum(
                c.expected_enrollment
                for c in db.query(OfferingCohort).filter(
                    OfferingCohort.offering_id == offering.id).all()
            )
            if offering.required_room_capacity is not None and total_enrollment > offering.required_room_capacity:
                blockers.append(PreflightBlocker(
                    code="ENROLLMENT_EXCEEDS_ROOM_CAPACITY",
                    message=f"Offering {offering.id} enrollment {total_enrollment} exceeds room capacity {offering.required_room_capacity}",
                    subject_type="offering", subject_id=offering.id,
                ))

        # Draft submissions are a blocker for submitting the cycle.
        for sub in db.query(Submission).filter(
            Submission.cycle_id == cycle.id, Submission.status == SUB_DRAFT).all():
            warnings.append(PreflightBlocker(
                code="SUBMISSION_DRAFT",
                message=f"Submission {sub.id} (unit {sub.unit_id}) is still a draft",
                subject_type="submission", subject_id=sub.id,
            ))

    _audit(db, "preflight", org_id, current_user.id, "cycle", cycle_id,
           {"blockers": len(blockers), "warnings": len(warnings)})
    db.commit()
    return PreflightResult(can_submit=not blockers, blockers=blockers, warnings=warnings)


# ------------------------------------------------------------------ audit
@router.get("/audit-events", response_model=List[DomainAuditEventRead])
def list_audit_events(
    subject_type: Optional[str] = None,
    subject_id: Optional[int] = None,
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    q = db.query(DomainAuditEvent).filter(DomainAuditEvent.organization_id == org_id)
    if subject_type is not None:
        q = q.filter(DomainAuditEvent.subject_type == subject_type)
    if subject_id is not None:
        q = q.filter(DomainAuditEvent.subject_id == subject_id)
    return q.order_by(DomainAuditEvent.id.desc()).limit(limit).all()
