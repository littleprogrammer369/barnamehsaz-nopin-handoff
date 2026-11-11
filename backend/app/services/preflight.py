"""Global preflight service for Phase 4 (07 پیش‌شرط Preflight).

Runs the full set of cycle-level checks before a solver run:
unit participation, submissions, shared-offering approvals (including
stale flags), meeting requirements, Q12 resource nominations, resource
availability, room capacity.

Blocker vs. warning (07: Preflight blocker را رفع‌پذیر توضیح بده و
لینک مستقیم به فرم اصلاح بده؛ warning از blocker جدا باشد):
- Blockers prevent a solve; warnings are surfaced but do not block.
Every issue carries a ``code`` (machine-readable) and a ``form_path``
hint pointing to the fix form.
"""
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.phase2 import (
    PlanningCycle,
    CycleUnit,
    ResourceAvailability,
    CourseOffering,
    OfferingUnit,
    OfferingCohort,
    MeetingRequirement,
    ResourceCommitment,
)
from app.models.phase3 import (
    Submission,
    SharedOfferingApproval,
    SUB_APPROVED,
    APPROVAL_UNIT_APPROVED,
)


class PreflightIssue(BaseModel):
    code: str
    message: str
    subject_type: Optional[str] = None
    subject_id: Optional[int] = None
    form_path: Optional[str] = None


class PreflightResult(BaseModel):
    can_submit: bool
    blockers: List[PreflightIssue]
    warnings: List[PreflightIssue]
    cycle_id: Optional[int] = None


def run_preflight(
    db: Session,
    cycle: PlanningCycle,
    actor_user_id: Optional[int] = None,
) -> PreflightResult:
    """Global preflight for one PlanningCycle (07 پیش‌شرط).

    Checks (blockers → 07 solve blocker; warnings → surfaced only):
    - CYCLE_NOT_SOLVABLE, UNIT_UNJOINED, SUBMISSION_MISSING /
      SUBMISSION_NOT_APPROVED, SHARED_OFFERING_UNAPPROVED /
      SHARED_OFFERING_STALE, MEETING_REQUIREMENT_MISSING /
      DUPLICATE_MEETING_REQUIREMENT, ENROLLMENT_EXCEEDS_ROOM_CAPACITY,
      Q12_RESOURCES_NOT_NOMINATED / Q12_MULTIPLE_RESOURCE_NOMINATIONS.
    Warnings: NO_RESOURCE_AVAILABILITY, RESOURCE_HEAVILY_COMMITTED.
    """
    blockers: List[PreflightIssue] = []
    warnings: List[PreflightIssue] = []

    if cycle.status not in ("submitted", "approved", "published"):
        blockers.append(PreflightIssue(
            code="CYCLE_NOT_SOLVABLE",
            message=f"Cycle {cycle.id} status is '{cycle.status}'; "
                    "solve requires status 'submitted' or later",
            subject_type="cycle", subject_id=cycle.id,
            form_path="/phases/3/submissions",
        ))
        return PreflightResult(can_submit=False, blockers=blockers,
                               warnings=warnings, cycle_id=cycle.id)

    members = db.query(CycleUnit).filter(CycleUnit.cycle_id == cycle.id).all()
    member_unit_ids = {m.unit_id for m in members}

    offerings = (
        db.query(CourseOffering)
        .filter(CourseOffering.planning_cycle_id == cycle.id)
        .all()
    )
    offering_unit_ids: set = set()
    for off in offerings:
        for ou in db.query(OfferingUnit).filter(OfferingUnit.offering_id == off.id).all():
            offering_unit_ids.add(ou.unit_id)

    for uid in offering_unit_ids:
        if uid not in member_unit_ids:
            blockers.append(PreflightIssue(
                code="UNIT_UNJOINED",
                message=f"Unit {uid} participates in offerings but is not a "
                        "cycle member",
                subject_type="unit", subject_id=uid,
                form_path="/phases/2/cycles/join",
            ))
        sub = (
            db.query(Submission)
            .filter(Submission.cycle_id == cycle.id,
                    Submission.unit_id == uid)
            .first()
        )
        if sub is None:
            blockers.append(PreflightIssue(
                code="SUBMISSION_MISSING",
                message=f"Unit {uid} has no submission for this cycle",
                subject_type="submission",
                form_path=f"/phases/3/submissions?cycle_id={cycle.id}&unit_id={uid}",
            ))
        elif sub.status != SUB_APPROVED:
            blockers.append(PreflightIssue(
                code="SUBMISSION_NOT_APPROVED",
                message=f"Unit {uid} submission is '{sub.status}', "
                        "approval required before solve",
                subject_type="submission", subject_id=sub.id,
                form_path=f"/phases/3/submissions/{sub.id}",
            ))

    for offering in offerings:
        participants = (
            db.query(OfferingUnit)
            .filter(OfferingUnit.offering_id == offering.id)
            .all()
        )
        is_shared = len(participants) > 1

        # shared-offering approvals (fresh, not stale)
        if is_shared:
            approvals = {
                a.unit_id: a
                for a in (
                    db.query(SharedOfferingApproval)
                    .filter(SharedOfferingApproval.offering_id == offering.id)
                    .all()
                )
            }
            for p in participants:
                a = approvals.get(p.unit_id)
                if a is None:
                    blockers.append(PreflightIssue(
                        code="SHARED_OFFERING_UNAPPROVED",
                        message=f"Shared offering {offering.id} lacks an "
                                f"approval row from unit {p.unit_id}",
                        subject_type="offering", subject_id=offering.id,
                        form_path=f"/phases/3/offerings/{offering.id}/approvals",
                    ))
                elif a.stale:
                    blockers.append(PreflightIssue(
                        code="SHARED_OFFERING_STALE",
                        message=f"Shared offering {offering.id} approval from "
                                f"unit {p.unit_id} is stale "
                                f"({a.stale_reason or 'data changed'})",
                        subject_type="offering", subject_id=offering.id,
                        form_path=f"/phases/3/offering_approvals"
                                  f"?offering_id={offering.id}",
                    ))
                elif a.status != APPROVAL_UNIT_APPROVED:
                    blockers.append(PreflightIssue(
                        code="SHARED_OFFERING_UNAPPROVED",
                        message=f"Shared offering {offering.id} approval from "
                                f"unit {p.unit_id} is '{a.status}'",
                        subject_type="offering", subject_id=offering.id,
                        form_path=f"/phases/3/offering_approvals"
                                  f"?offering_id={offering.id}",
                    ))

        # meeting requirement
        mrs = (
            db.query(MeetingRequirement)
            .filter(MeetingRequirement.offering_id == offering.id)
            .all()
        )
        if len(mrs) == 0:
            blockers.append(PreflightIssue(
                code="MEETING_REQUIREMENT_MISSING",
                message=f"Offering {offering.id} has no meeting requirement",
                subject_type="offering", subject_id=offering.id,
                form_path=f"/phases/2/offerings/{offering.id}/meeting",
            ))
        elif len(mrs) > 1:
            blockers.append(PreflightIssue(
                code="DUPLICATE_MEETING_REQUIREMENT",
                message=f"Offering {offering.id} has {len(mrs)} meeting "
                        "requirements (max 1)",
                subject_type="offering", subject_id=offering.id,
            ))

        # enrollment vs. room capacity
        total_enrollment = sum(
            c.expected_enrollment
            for c in (
                db.query(OfferingCohort)
                .filter(OfferingCohort.offering_id == offering.id)
                .all()
            )
        )
        if (offering.required_room_capacity is not None
                and total_enrollment > offering.required_room_capacity):
            blockers.append(PreflightIssue(
                code="ENROLLMENT_EXCEEDS_ROOM_CAPACITY",
                message=f"Offering {offering.id} enrollment {total_enrollment} "
                        f"exceeds room capacity {offering.required_room_capacity}",
                subject_type="offering", subject_id=offering.id,
            ))

        # Q12 resource nomination
        nominations = [p for p in participants
                       if p.room_resource_id is not None
                       or p.instructor_resource_id is not None]
        if is_shared:
            if not nominations:
                blockers.append(PreflightIssue(
                    code="Q12_RESOURCES_NOT_NOMINATED",
                    message=f"Shared offering {offering.id}: no unit has "
                            "nominated the canonical room/instructor resources",
                    subject_type="offering", subject_id=offering.id,
                    form_path=f"/phases/3/offerings/{offering.id}/resources",
                ))
            elif len(nominations) > 1:
                blockers.append(PreflightIssue(
                    code="Q12_MULTIPLE_RESOURCE_NOMINATIONS",
                    message=f"Shared offering {offering.id}: "
                            f"{len(nominations)} units nominated resources; "
                            "only the proposing unit may nominate "
                            "(single resource identity, 06)",
                    subject_type="offering", subject_id=offering.id,
                ))
        elif not nominations:
            blockers.append(PreflightIssue(
                code="Q12_RESOURCES_NOT_NOMINATED",
                message=f"Offering {offering.id}: room/instructor resources "
                        "were not nominated",
                subject_type="offering", subject_id=offering.id,
                form_path=f"/phases/3/offerings/{offering.id}/resources",
            ))

        for p in nominations:
            for rid in filter(None,
                              (p.room_resource_id,
                               p.instructor_resource_id)):
                av = (
                    db.query(ResourceAvailability)
                    .filter(ResourceAvailability.resource_id == rid,
                            ResourceAvailability.cycle_id == cycle.id)
                    .count()
                )
                if av == 0:
                    warnings.append(PreflightIssue(
                        code="NO_RESOURCE_AVAILABILITY",
                        message=f"Resource {rid} nominated for offering "
                                f"{offering.id} has no availability window in "
                                f"cycle {cycle.id}; availability is "
                                "'unknown' and may make the run infeasible",
                        subject_type="resource", subject_id=rid,
                    ))

    # duplicate resource warnings (07 preflight: unresolved duplicates
    # block the solve or are resolved by the manager with a reason)
    room_by_resource: dict = {}
    for offering in offerings:
        for p in db.query(OfferingUnit).filter(
                OfferingUnit.offering_id == offering.id).all():
            if p.room_resource_id is not None:
                room_by_resource.setdefault(
                    p.room_resource_id, []).append(offering.id)
    for rid, oids in room_by_resource.items():
        if len(oids) < 2:
            continue
        commitments = (
            db.query(ResourceCommitment)
            .filter(ResourceCommitment.resource_id == rid,
                    ResourceCommitment.cycle_id == cycle.id)
            .count()
        )
        if commitments > 0:
            warnings.append(PreflightIssue(
                code="RESOURCE_HEAVILY_COMMITTED",
                message=f"Resource {rid} is used by {len(oids)} offerings "
                        "and has commitments; solver may be infeasible",
                subject_type="resource", subject_id=rid,
            ))

    return PreflightResult(
        can_submit=not blockers,
        blockers=blockers,
        warnings=warnings,
        cycle_id=cycle.id,
    )
