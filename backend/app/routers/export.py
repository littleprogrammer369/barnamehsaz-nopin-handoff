"""Export/publish routes (08).

- POST /phase4/runs/{run_id}/publish : manager confirmation of a feasible run
- GET  /phase4/runs/{run_id}/export/excel : downloadable workbook (.xlsx)
- GET  /phase4/runs/{run_id}/export/pdf  : downloadable PDF (.pdf)

All endpoints are auth-gated and org-scoped. No hard-coded host; the API
is consumed under the same-origin /api/v1 prefix on the browser side (03/05).
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.base import User
from app.models.phase4 import (
    PublishedSchedule, PUBLISHED_STATUS_DRAFT, PUBLISHED_STATUS_CURRENT,
    PUBLISHED_STATUS_PREVIOUS, PUBLISHED_STATUS_STALE, SolverRun,
)
from app.routers.phase2 import get_current_user
from app.services.export_excel import export_published_schedule_xlsx
from app.services.export_pdf import export_published_schedule_pdf
from app.services.submission_tracking import get_submission_status

router = APIRouter(prefix="/phase4", tags=["phase4"])


def _find_or_404(db: Session, run_id: int) -> SolverRun:
    run = db.get(SolverRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _resolve_published_or_create(
    db: Session, run: SolverRun, requested_version: Optional[float], user: User
) -> PublishedSchedule:
    if run.stale:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RUN_STALE",
                "message": "Cannot publish a stale run; data changed after solve",
                "run_id": run.id,
            },
        )
    if run.status != "feasible":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_FEASIBLE",
                "run_id": run.id,
                "status": run.status,
                "message": "Only feasible runs may be published",
            },
        )

    existing = (
        db.query(PublishedSchedule)
        .filter(
            PublishedSchedule.run_id == run.id,
            PublishedSchedule.organization_id == run.organization_id,
            PublishedSchedule.cycle_id == run.cycle_id,
            PublishedSchedule.status.in_(
                (PUBLISHED_STATUS_DRAFT, PUBLISHED_STATUS_CURRENT, PUBLISHED_STATUS_PREVIOUS)
            ),
        )
        .order_by(PublishedSchedule.version.desc())
        .first()
    )
    version = float(requested_version or 0)
    if existing is not None:
        return existing

    ps = PublishedSchedule(
        run_id=run.id,
        cycle_id=run.cycle_id,
        organization_id=run.organization_id,
        version=version,
        input_snapshot=run.input_snapshot,
        result_snapshot=run.result_snapshot,
        source_run_id=run.id,
        actor_user_id=user.id,
        status=PUBLISHED_STATUS_DRAFT,
        stale=False,
    )
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


def _promote_current(db: Session, ps: PublishedSchedule) -> PublishedSchedule:
    current = db.query(PublishedSchedule).filter(
        PublishedSchedule.organization_id == ps.organization_id,
        PublishedSchedule.cycle_id == ps.cycle_id,
        PublishedSchedule.status == PUBLISHED_STATUS_CURRENT,
    )
    for row in current.all():
        if row.version <= ps.version:
            row.status = PUBLISHED_STATUS_PREVIOUS
    ps.status = PUBLISHED_STATUS_CURRENT
    db.commit()
    db.refresh(ps)
    return ps


@router.post("/runs/{run_id}/publish", status_code=status.HTTP_201_CREATED)
def publish_run(
    run_id: int,
    requested_version: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager confirms a feasible run; idempotent create-or-reuse.
    
    Requires: All units in the planning cycle must be approved before publishing.
    """
    run = _find_or_404(db, run_id)
    
    # GATE: Check cycle-specific unit approval requirement
    status_obj = get_submission_status(run.cycle_id, db)
    total_units = status_obj["total_units"]
    approved_count = status_obj["approved_count"]
    
    if approved_count < total_units:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Publishing requires all {total_units} units to be approved. Currently {approved_count}/{total_units} units are approved."
        )
    
    ps = _resolve_published_or_create(db, run, requested_version, current_user)
    ps = _promote_current(db, ps)
    return {
        "run_id": run_id,
        "version": ps.version,
        "status": ps.status,
        "cycle_id": run.cycle_id,
        "actor": f"#{ps.actor_user_id}",
    }


def _find_published(db: Session, run: SolverRun):
    return (
        db.query(PublishedSchedule)
        .filter(
            PublishedSchedule.run_id == run.id,
            PublishedSchedule.organization_id == run.organization_id,
            PublishedSchedule.cycle_id == run.cycle_id,
            PublishedSchedule.status.in_((PUBLISHED_STATUS_CURRENT, PUBLISHED_STATUS_PREVIOUS)),
        )
        .order_by(PublishedSchedule.version.desc())
        .first()
    )


@router.get("/runs/{run_id}/export/excel")
def download_excel(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return an .xlsx workbook for the published schedule of this run.
    
    Unit managers see only assignments from their unit's offerings.
    Admin sees all assignments.
    """
    from app.core.rbac import get_user_role, ROLE_UNIT_MANAGER, get_unit_for_user
    
    run = _find_or_404(db, run_id)
    ps = _find_published(db, run)
    if ps is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_PUBLISHED", "run_id": run_id, "message": "No published schedule found"},
        )
    if ps.stale:
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_STALE", "message": ps.stale_reason or "stale published schedule"},
        )
    
    # Determine unit_id for filtering
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == ps.cycle_id).first()
    user_role = get_user_role(current_user.id, cycle.organization_id, db)
    unit_id = None
    
    if user_role == ROLE_UNIT_MANAGER:
        unit_id = get_unit_for_user(current_user.id, cycle.organization_id, db)
        if unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )
    
    buf = export_published_schedule_xlsx(db, ps, unit_id=unit_id)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="schedule_{run_id}_v{ps.version}.xlsx"'},
    )


@router.get("/runs/{run_id}/export/pdf")
def download_pdf(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a .pdf for the published schedule.
    
    Unit managers see only assignments from their unit's offerings.
    Admin sees all assignments.
    """
    from app.core.rbac import get_user_role, ROLE_UNIT_MANAGER, get_unit_for_user
    
    run = _find_or_404(db, run_id)
    ps = _find_published(db, run)
    if ps is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_PUBLISHED", "run_id": run_id, "message": "No published schedule found"},
        )
    if ps.stale:
        raise HTTPException(
            status_code=409,
            detail={"code": "RUN_STALE", "message": ps.stale_reason or "stale published schedule"},
        )
    
    # Determine unit_id for filtering
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == ps.cycle_id).first()
    user_role = get_user_role(current_user.id, cycle.organization_id, db)
    unit_id = None
    
    if user_role == ROLE_UNIT_MANAGER:
        unit_id = get_unit_for_user(current_user.id, cycle.organization_id, db)
        if unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )
    
    buf = export_published_schedule_pdf(db, ps, unit_id=unit_id)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="schedule_{run_id}_v{ps.version}.pdf"'},
    )
