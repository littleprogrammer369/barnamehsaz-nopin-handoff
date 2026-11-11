"""Submission workflow tracking and status checks.

Tracks progression from 0/5 submitted units to 5/5 and gating for preflight/publish.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.phase2 import PlanningCycle, Unit, CycleUnit
from app.models.phase3 import Submission, SUB_SUBMITTED, SUB_APPROVED


def count_units_in_cycle(cycle_id: int, db: Session) -> int:
    """Count total units participating in a planning cycle."""
    return db.query(func.count(CycleUnit.id)).filter(
        CycleUnit.cycle_id == cycle_id
    ).scalar() or 0


def count_submitted_in_cycle(cycle_id: int, db: Session) -> int:
    """Count units with submitted or approved submissions in a cycle."""
    return db.query(func.count(Submission.id)).filter(
        Submission.cycle_id == cycle_id,
        Submission.status.in_([SUB_SUBMITTED, SUB_APPROVED])
    ).scalar() or 0


def count_approved_in_cycle(cycle_id: int, db: Session) -> int:
    """Count units with approved submissions in a cycle."""
    return db.query(func.count(Submission.id)).filter(
        Submission.cycle_id == cycle_id,
        Submission.status == SUB_APPROVED
    ).scalar() or 0


def get_submission_status(cycle_id: int, db: Session) -> dict:
    """Get submission progress for a cycle.
    
    Returns dict with:
      - total_units: total units in cycle
      - submitted_count: units with submitted/approved status
      - approved_count: units with approved status
      - can_preflight: submitted_count == total_units
      - can_publish: approved_count == total_units
    """
    total = count_units_in_cycle(cycle_id, db)
    submitted = count_submitted_in_cycle(cycle_id, db)
    approved = count_approved_in_cycle(cycle_id, db)
    
    return {
        "total_units": total,
        "submitted_count": submitted,
        "approved_count": approved,
        "can_preflight": submitted == total and total > 0,
        "can_publish": approved == total and total > 0,
    }
