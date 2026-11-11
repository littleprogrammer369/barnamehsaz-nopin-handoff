"""Stale-marking service for Phase 4 (06 step 6 / 07 خروجی).

تغییر دادهٔ مؤثر پس از approval:
- approvalهای مشترک (SharedOfferingApproval) از طریق flag ``stale``
  علامت‌گذاری می‌شوند (history پاک نمی‌شود، باید دوباره confirm شوند).
- solver runs‌های non-stale همان cycle علامت ``stale`` می‌گیرند؛
  run‌ها immutable می‌مانند — فقط flag/دلیل آن‌ها به‌روز می‌شود.

All mutations happen inside the caller's transaction and are committed
together with the OfferingCorrection row, so history + flags are
atomic.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.phase2 import CourseOffering
from app.models.phase3 import SharedOfferingApproval
from app.models.phase4 import OfferingCorrection, SolverRun, RUN_FEASIBLE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mark_offering_stale(
    db: Session,
    offering: CourseOffering,
    correction: OfferingCorrection,
    actor_user_id: Optional[int],
) -> bool:
    """Mark approvals + live solver runs of an offering stale.

    Returns True when at least one approval was flagged stale.
    """
    reason = f"offering_correction#{correction.id} field={correction.field}"
    approvals = (
        db.query(SharedOfferingApproval)
        .filter(SharedOfferingApproval.offering_id == offering.id)
        .all()
    )
    marked = False
    for approval in approvals:
        if not approval.stale:
            approval.stale = True
            approval.stale_reason = reason
            approval.stale_at = _now()
            marked = True

    runs = (
        db.query(SolverRun)
        .filter(SolverRun.cycle_id == offering.planning_cycle_id,
                SolverRun.stale.is_(False))
        .all()
    )
    for run in runs:
        run.stale = True
        run.stale_reason = reason
    return marked
