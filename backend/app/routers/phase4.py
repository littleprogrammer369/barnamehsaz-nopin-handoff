"""Phase 4 router: global solver, run history, run comparison, and the
manager correction track with stale-marking of approvals.

- ``POST /solve``: preflight-gated global solve of one PlanningCycle
  (07 hard constraints + soft objectives), immutable snapshots.
- ``GET  /runs`` / ``GET /runs/{id}`` / ``GET /runs/compare``: history and
  comparison of two runs (07 خروجی/مقایسه).
- ``POST /corrections``: admin manual correction of offering data
  (06 manager correction) — append-only, marks affected approvals and
  non-stale solver runs stale.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.base import User, Membership
from app.models.phase2 import PlanningCycle, CourseOffering
from app.models.phase4 import (
    OfferingCorrection, SolverAssignment, SolverRun,
    RUN_FAILED, RUN_FEASIBLE, RUN_INFEASIBLE,
)
from app.routers.phase2 import get_current_user
from app.services.preflight import run_preflight
from app.services.solver import run_solve
from app.services.stale import mark_offering_stale
from app.schemas.phase3 import PreflightBlocker

router = APIRouter(prefix="/phase4", tags=["phase4"])


def _org_id_for(user: User, db: Session) -> int:
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if membership is None:
        raise HTTPException(status_code=403, detail="User has no organization membership")
    return membership.organization_id


def _require_admin(user: User, db: Session) -> None:
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.role == "admin")
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="admin role required")


def _audit(db: Session, action: str, org_id: int, actor_user_id: int,
           subject_type: str, subject_id: Optional[int], detail: Optional[dict] = None):
    from app.models.phase3 import DomainAuditEvent
    db.add(DomainAuditEvent(
        action=action, organization_id=org_id, actor_user_id=actor_user_id,
        subject_type=subject_type, subject_id=subject_id, detail=detail,
    ))


# ------------------------------------------------------------------ schemas
class SolveRequest(BaseModel):
    cycle_id: int
    # Optional 07 objective weights; when omitted, defaults are recorded in
    # the run snapshot so the exact objective of every historical run stays
    # visible (soft objectives must be config/version-aware).
    objective_weights: Optional[dict] = None


class SolveResult(BaseModel):
    run_id: int
    cycle_id: int
    status: str
    objective_score: Optional[float]
    stale: bool
    can_publish: bool
    blockers: List[PreflightBlocker]
    warnings: List[PreflightBlocker]
    infeasible_causes: List[dict]


class SolverRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cycle_id: int
    organization_id: int
    status: str
    actor_user_id: Optional[int]
    objective_score: Optional[float]
    stale: bool
    stale_reason: Optional[str]
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class SolverAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    offering_id: int
    resource_id: Optional[int]
    occurrence_no: int
    weekday: Optional[int]
    start_hhmm: Optional[str]
    end_hhmm: Optional[str]
    meetings_per_week: Optional[int]
    duration_minutes: Optional[int]


class RunCompareSide(BaseModel):
    run_id: int
    status: str
    objective_score: Optional[float]
    stale: bool


class RunComparison(BaseModel):
    a: RunCompareSide
    b: RunCompareSide
    shared_offering_changes: List[dict]
    schedule_changes: List[dict]
    score_delta: Optional[float]
    unresolved_warnings: List[dict]


class CorrectionRequest(BaseModel):
    """Admin correction of a mutable offering field (06 manager correction)."""

    cycle_id: int
    offering_id: int
    field: str = Field(pattern=r"^[a-z_]{3,40}$")
    before_value: Optional[str] = None
    after_value: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=3, max_length=2000)


class CorrectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    offering_id: int
    cycle_id: int
    organization_id: int
    field: str
    before_value: Optional[str]
    after_value: Optional[str]
    reason: str
    actor_user_id: Optional[int]
    approvals_marked_stale: bool
    created_at: datetime

# ------------------------------------------------------------------ solve
@router.post("/solve", response_model=SolveResult)
def solve(
    body: SolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the global solver for one PlanningCycle.

    Preflight blockers block the run (07 پیش‌شرط); warnings are recorded
    but do not block. All solver inputs are read into an immutable
    snapshot (07 hard #11) — later data changes never mutate this run.
    """
    org_id = _org_id_for(current_user, db)
    cycle = (
        db.query(PlanningCycle)
        .filter(PlanningCycle.id == body.cycle_id,
                PlanningCycle.organization_id == org_id)
        .first()
    )
    if cycle is None:
        raise HTTPException(status_code=404,
                            detail="Cycle not found in this organization")

    from app.services.preflight import PreflightResult as _PR
    pre: _PR = run_preflight(db, cycle, current_user.id)
    if not pre.can_submit:
        _audit(db, "solve_blocked", org_id, current_user.id, "cycle", cycle.id,
               {"blockers": [b.code for b in pre.blockers]})
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PREFLIGHT_BLOCKED",
                "cycle_id": cycle.id,
                "blockers": [b.model_dump() for b in pre.blockers],
                "warnings": [b.model_dump() for b in pre.warnings],
            },
        )

    run = run_solve(db, cycle, current_user.id,
                    objective_weights=body.objective_weights)
    result = run.result_snapshot or {}
    can_publish = run.status == RUN_FEASIBLE and not run.stale
    blockers: List[PreflightBlocker] = []
    if run.status == RUN_INFEASIBLE:
        blockers = [
            PreflightBlocker(code=c.get("code", "INFEASIBLE"),
                             message=c.get("message", ""),
                             subject_type=c.get("subject_type", "cycle"),
                             subject_id=c.get("subject_id", cycle.id))
            for c in result.get("infeasible_causes", [])
        ]
    return SolveResult(
        run_id=run.id,
        cycle_id=cycle.id,
        status=run.status,
        objective_score=run.objective_score,
        stale=run.stale,
        can_publish=can_publish,
        blockers=blockers,
        warnings=[PreflightBlocker(
            code=w.get("code", "WARNING"),
            message=w.get("message", ""),
            subject_type=w.get("subject_type"),
            subject_id=w.get("subject_id"),
        ) for w in result.get("warnings", [])],
        infeasible_causes=result.get("infeasible_causes", []),
    )


# ------------------------------------------------------------------ history
@router.get("/runs", response_model=List[SolverRunRead])
def list_runs(
    cycle_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """History of solver runs — runs are immutable (07: Runهای قبلی
    immutable بمانند)."""
    org_id = _org_id_for(current_user, db)
    q = db.query(SolverRun).filter(SolverRun.organization_id == org_id)
    if cycle_id is not None:
        q = q.filter(SolverRun.cycle_id == cycle_id)
    return (
        q.order_by(SolverRun.created_at.desc(), SolverRun.id.desc())
        .limit(200)
        .all()
    )


@router.get("/runs/compare", response_model=RunComparison)
def compare_runs(
    a: int, b: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """07 مقایسهٔ دو Run: schedule, score, unresolved warnings, key diffs.
    
    Unit managers see only schedule changes from their unit's offerings.
    """
    from app.core.rbac import get_user_role, ROLE_UNIT_MANAGER, get_unit_for_user
    from app.models.phase2 import OfferingUnit
    
    org_id = _org_id_for(current_user, db)
    q = db.query(SolverRun).filter(
        SolverRun.id.in_([a, b]), SolverRun.organization_id == org_id)
    runs = {r.id: r for r in q.all()}
    if len(runs) != 2:
        raise HTTPException(status_code=404, detail="One or both runs not found")
    run_a, run_b = runs[a], runs[b]
    if run_a.cycle_id != run_b.cycle_id:
        raise HTTPException(
            status_code=409,
            detail="Cannot compare runs of different PlanningCycles")

    # Determine unit access for unit_managers
    user_role = get_user_role(current_user.id, org_id, db)
    unit_id = None
    
    if user_role == ROLE_UNIT_MANAGER:
        unit_id = get_unit_for_user(current_user.id, org_id, db)
        if unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )

    def _sched(run: SolverRun) -> dict:
        q = db.query(SolverAssignment).filter(SolverAssignment.run_id == run.id)
        
        # Filter by unit if needed
        if unit_id is not None:
            q = (
                q.join(OfferingUnit, SolverAssignment.offering_id == OfferingUnit.offering_id)
                .filter(OfferingUnit.unit_id == unit_id)
            )
        
        rows = q.all()
        return {
            (x.offering_id, x.occurrence_no): (x.weekday, x.start_hhmm, x.end_hhmm, x.resource_id)
            for x in rows
        }

    sched_a, sched_b = _sched(run_a), _sched(run_b)
    schedule_changes: List[dict] = []
    for key in sorted(set(sched_a) | set(sched_b)):
        if key not in sched_a:
            schedule_changes.append({"offering_id": key[0], "occurrence_no": key[1],
                                    "change": "added_in_b", "b": list(sched_b[key])})
        elif key not in sched_b:
            schedule_changes.append({"offering_id": key[0], "occurrence_no": key[1],
                                    "change": "removed_in_b", "a": list(sched_a[key])})
        elif sched_a[key] != sched_b[key]:
            schedule_changes.append({"offering_id": key[0], "occurrence_no": key[1],
                                    "change": "moved",
                                    "a": list(sched_a[key]), "b": list(sched_b[key])})
    shared_offering_changes = [
        c for c in schedule_changes
        if db.query(OfferingCorrection).filter_by(offering_id=c["offering_id"]).count()
    ]
    unresolved: List[dict] = []
    for run in (run_a, run_b):
        for w in (run.result_snapshot or {}).get("warnings", []):
            unresolved.append({"run_id": run.id, **w})

    score_delta = None
    if run_a.objective_score is not None and run_b.objective_score is not None:
        score_delta = run_b.objective_score - run_a.objective_score

    return RunComparison(
        a=RunCompareSide(run_id=a, status=run_a.status,
                         objective_score=run_a.objective_score,
                         stale=run_a.stale),
        b=RunCompareSide(run_id=b, status=run_b.status,
                         objective_score=run_b.objective_score,
                         stale=run_b.stale),
        shared_offering_changes=shared_offering_changes,
        schedule_changes=schedule_changes,
        score_delta=score_delta,
        unresolved_warnings=unresolved,
    )


@router.get("/runs/{run_id}", response_model=dict)
def get_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full run record: input snapshot, result snapshot, and assignments.
    
    Unit managers see only assignments from their unit's offerings.
    """
    from app.core.rbac import get_user_role, ROLE_UNIT_MANAGER, get_unit_for_user
    from app.models.phase2 import OfferingUnit
    
    org_id = _org_id_for(current_user, db)
    run = (
        db.query(SolverRun)
        .filter(SolverRun.id == run_id, SolverRun.organization_id == org_id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Determine unit access for unit_managers
    user_role = get_user_role(current_user.id, org_id, db)
    unit_id = None
    
    if user_role == ROLE_UNIT_MANAGER:
        unit_id = get_unit_for_user(current_user.id, org_id, db)
        if unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )
    
    # Query assignments
    q = db.query(SolverAssignment).filter(SolverAssignment.run_id == run.id)
    
    # Filter by unit if needed
    if unit_id is not None:
        q = (
            q.join(OfferingUnit, SolverAssignment.offering_id == OfferingUnit.offering_id)
            .filter(OfferingUnit.unit_id == unit_id)
        )
    
    assignments = q.order_by(SolverAssignment.occurrence_no, SolverAssignment.id).all()
    
    return {
        "run": SolverRunRead.model_validate(run).model_dump(),
        "input_snapshot": run.input_snapshot,
        "result_snapshot": run.result_snapshot,
        "assignments": [SolverAssignmentRead.model_validate(a).model_dump()
                       for a in assignments],
    }


# ------------------------------------------------------------------ corrections
@router.post("/corrections", response_model=CorrectionRead)
def record_correction(
    body: CorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only manual correction (06: مدیر کل می‌تواند manual correction
    انجام دهد فقط با نقش مناسب و ثبت actor/reason).

    The unit's original data is preserved in the submission history; this
    row records the managerial version. After a correction touching
    approval-affecting data:
    - existing shared-offering approvals are marked stale (history kept);
    - all non-stale solver runs of the cycle are marked stale.
    """
    _require_admin(current_user, db)
    org_id = _org_id_for(current_user, db)
    cycle = (
        db.query(PlanningCycle)
        .filter(PlanningCycle.id == body.cycle_id,
                PlanningCycle.organization_id == org_id)
        .first()
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found in this organization")
    offering = (
        db.query(CourseOffering)
        .filter(CourseOffering.id == body.offering_id,
                CourseOffering.planning_cycle_id == body.cycle_id)
        .first()
    )
    if offering is None:
        raise HTTPException(status_code=404, detail="Offering not found in this cycle")

    correction = OfferingCorrection(
        offering_id=offering.id,
        cycle_id=cycle.id,
        organization_id=org_id,
        field=body.field,
        before_value=body.before_value,
        after_value=body.after_value,
        reason=body.reason,
        actor_user_id=current_user.id,
    )
    db.add(correction)
    db.flush()  # id is needed for the stale reason
    approvals_marked = mark_offering_stale(db, offering, correction, current_user.id)
    correction.approvals_marked_stale = approvals_marked
    _audit(db, "offering_correction", org_id, current_user.id,
           "offering", offering.id, {
               "field": body.field,
               "approvals_marked_stale": approvals_marked,
           })
    db.commit()
    db.refresh(correction)
    return correction


@router.get("/corrections", response_model=List[CorrectionRead])
def list_corrections(
    cycle_id: Optional[int] = None,
    offering_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Append-only correction history (05: قابل‌ردیابی)."""
    org_id = _org_id_for(current_user, db)
    q = db.query(OfferingCorrection).filter(
        OfferingCorrection.organization_id == org_id)
    if cycle_id is not None:
        q = q.filter(OfferingCorrection.cycle_id == cycle_id)
    if offering_id is not None:
        q = q.filter(OfferingCorrection.offering_id == offering_id)
    return (
        q.order_by(OfferingCorrection.created_at.desc(),
                   OfferingCorrection.id.desc())
        .limit(200)
        .all()
    )
