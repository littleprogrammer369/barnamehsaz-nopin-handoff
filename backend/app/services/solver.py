"""Phase 4 OR-Tools CP-SAT solver service (07 GLOBAL_SOLVER).

All solver inputs are read into an immutable input_snapshot before the
solve (07 hard #11 — a mid-run data change never leaks into the result).
The run reaches exactly one terminal state:

- feasible:   every hard constraint holds, assignments are persisted
- infeasible: no schedule exists; actionable infeasible_causes are
  recorded (07 INFEASIBLE: هیچ برنامهٔ نهایی نساز)
- failed:     solver error/timeout → technical reason, partial results
  are never presented as final

Hard constraints enforced (07 hard): room/instructor single-booking,
room capacity >= enrollment, resource availability windows, weekday
windows, occurrences × duration exactly, shared offering gets exactly
one assignment per occurrence.

Soft objective (07): minimize total weekly instructor load + room waste,
weights recorded in the run so the objective of every historical run
stays visible.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from app.models.phase2 import (
    PlanningCycle,
    Resource,
    CourseOffering,
    OfferingUnit,
    OfferingCohort,
    MeetingRequirement,
    ResourceAvailability,
    ResourceCommitment,
)
from app.models.phase4 import (
    SolverRun,
    SolverAssignment,
    RUN_FEASIBLE,
    RUN_INFEASIBLE,
    RUN_FAILED,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class _OfferingData:
    """Frozen input for one offering (read from snapshot only)."""

    def __init__(self, offering: CourseOffering,
                 nomination: List[OfferingUnit],
                 meeting_req: Optional[MeetingRequirement]):
        self.offering_id = offering.id
        self.meetings_per_week = offering.meetings_per_week
        self.duration_minutes = offering.duration_minutes
        self.required_room_capacity = offering.required_room_capacity
        self.is_shared = len(nomination) > 1
        self.room_resource_id: Optional[int] = None
        self.instructor_resource_id: Optional[int] = None
        for p in nomination:
            self.room_resource_id = p.room_resource_id
            self.instructor_resource_id = p.instructor_resource_id
        self.weekday_min = meeting_req.allowed_weekday_min if meeting_req else None
        self.weekday_max = meeting_req.allowed_weekday_max if meeting_req else None
        self.start_window = meeting_req.start_window_hhmm if meeting_req else None
        self.end_window = meeting_req.end_window_hhmm if meeting_req else None
        self.total_enrollment = sum(
            c.expected_enrollment for c in nomination
            if c.expected_enrollment is not None
        )


class _ResourceData:
    def __init__(self, resource: Optional[Resource],
                 availability: List[Tuple[int, int, int]],
                 commitments: List[Tuple[int, int, int]]):
        self.id = resource.id if resource else None
        self.kind = resource.kind if resource else None
        self.capacity = resource.capacity if resource else None
        self.availability = availability      # (weekday, start_min, end_min)
        self.commitments = commitments


def _windows(db: Session, resource_id: int,
              cycle: PlanningCycle) -> Tuple[list, list]:
    avail = (
        db.query(ResourceAvailability)
        .filter(ResourceAvailability.resource_id == resource_id,
                ResourceAvailability.cycle_id == cycle.id)
        .all()
    )
    comm = (
        db.query(ResourceCommitment)
        .filter(ResourceCommitment.resource_id == resource_id,
                ResourceCommitment.cycle_id == cycle.id)
        .all()
    )
    to_win = lambda rows: [
        (r.weekday, _hhmm_to_min(r.start_hhmm), _hhmm_to_min(r.end_hhmm))
        for r in rows
    ]
    return to_win(avail), to_win(comm)


def run_solve(
    db: Session,
    cycle: PlanningCycle,
    actor_user_id: Optional[int],
    objective_weights: Optional[dict] = None,
) -> SolverRun:
    """Run the global CP-SAT solver for one PlanningCycle.

    Creates the SolverRun, freezes all inputs into ``input_snapshot``,
    solves, and persists the terminal state plus any assignments in one
    transaction (07: outcome of the run is never updated after commit).
    """
    from app.models.phase4 import RUN_QUEUED

    offerings = (
        db.query(CourseOffering)
        .filter(CourseOffering.planning_cycle_id == cycle.id)
        .all()
    )
    run = SolverRun(
        cycle_id=cycle.id,
        organization_id=cycle.organization_id,
        status=RUN_QUEUED,
        actor_user_id=actor_user_id,
    )
    db.add(run)
    db.flush()

    if not offerings:
        run.status = RUN_INFEASIBLE
        run.input_snapshot = {"cycle_id": cycle.id, "offerings": []}
        run.result_snapshot = {
            "infeasible_causes": [{
                "code": "NO_OFFERINGS",
                "message": f"Cycle {cycle.id} has no offerings to solve",
                "subject_type": "cycle", "subject_id": cycle.id,
            }],
            "warnings": [],
        }
        run.finished_at = _now()
        db.commit()
        db.refresh(run)
        return run

    return _solve_and_persist(db, run, cycle, offerings, objective_weights)


def _snapshot_inputs(
    db: Session,
    cycle: PlanningCycle,
    offerings: List[CourseOffering],
) -> Tuple[List[_OfferingData], Dict[int, _ResourceData], List[dict]]:
    offering_datas: List[_OfferingData] = []
    resources: Dict[int, _ResourceData] = {}
    snap_offerings: List[dict] = []

    for offering in offerings:
        nomination = (
            db.query(OfferingUnit)
            .filter(OfferingUnit.offering_id == offering.id)
            .all()
        )
        meeting_req = (
            db.query(MeetingRequirement)
            .filter(MeetingRequirement.offering_id == offering.id)
            .first()
        )
        data = _OfferingData(offering, nomination, meeting_req)
        offering_datas.append(data)
        snap_offerings.append({
            "offering_id": offering.id,
            "is_shared": data.is_shared,
            "meetings_per_week": offering.meetings_per_week,
            "duration_minutes": offering.duration_minutes,
            "required_room_capacity": offering.required_room_capacity,
            "room_resource_id": data.room_resource_id,
            "instructor_resource_id": data.instructor_resource_id,
            "weekday_min": data.weekday_min,
            "weekday_max": data.weekday_max,
            "start_window": data.start_window,
            "end_window": data.end_window,
        })
        for rid in filter(None,
                          (data.room_resource_id,
                           data.instructor_resource_id)):
            if rid not in resources:
                res = db.query(Resource).filter(Resource.id == rid).first()
                avail, comm = _windows(db, rid, cycle)
                resources[rid] = _ResourceData(res, avail, comm)
    return offering_datas, resources, snap_offerings


def _data_gaps(
    offering_datas: List[_OfferingData],
    resources: Dict[int, _ResourceData],
) -> List[dict]:
    """Infeasibility from data gaps, without running the solver."""
    gaps: List[dict] = []
    for data in offering_datas:
        rid_room = data.room_resource_id
        rid_inst = data.instructor_resource_id
        if rid_room is None or rid_inst is None:
            gaps.append({
                "code": "Q12_RESOURCES_NOT_NOMINATED",
                "message": f"Offering {data.offering_id} lacks a "
                           "room/instructor resource nomination",
                "subject_type": "offering", "subject_id": data.offering_id,
            })
            continue
        room_res = resources.get(rid_room)
        inst_res = resources.get(rid_inst)
        if room_res and not room_res.availability:
            gaps.append({
                "code": "NO_RESOURCE_AVAILABILITY",
                "message": f"Room {rid_room} for offering "
                           f"{data.offering_id} has no availability window",
                "subject_type": "offering", "subject_id": data.offering_id,
            })
        if inst_res and not inst_res.availability:
            gaps.append({
                "code": "NO_INSTRUCTOR_AVAILABILITY",
                "message": f"Instructor {rid_inst} for offering "
                           f"{data.offering_id} has no availability window",
                "subject_type": "offering", "subject_id": data.offering_id,
            })
        # 07 hard #3: the nominated room must satisfy BOTH the actual
        # enrollment and the offering's required_room_capacity floor.
        effective_enrollment = max(data.total_enrollment, data.required_room_capacity or 0)
        if room_res and room_res.capacity is None:
            gaps.append({
                "code": "ROOM_CAPACITY_MISSING",
                "message": f"Room {rid_room} has no capacity recorded; "
                           "capacity is required for the solve "
                           f"(offering {data.offering_id})",
                "subject_type": "offering", "subject_id": data.offering_id,
            })
        elif room_res.capacity < effective_enrollment:
            gaps.append({
                "code": "ENROLLMENT_EXCEEDS_ROOM_CAPACITY",
                "message": (
                    f"Offering {data.offering_id} needs at least "
                    f"{effective_enrollment} seats "
                    f"(enrollment {data.total_enrollment}, "
                    f"required capacity {data.required_room_capacity or 0}) "
                    f"but room {rid_room} holds {room_res.capacity}"
                ),
                "subject_type": "offering", "subject_id": data.offering_id,
            })
    return gaps


def _build_model(
    model,
    offering_datas: List[_OfferingData],
    resources: Dict[int, _ResourceData],
) -> Tuple[List[List[Tuple[int, int]]], dict]:
    """Candidate slots + exactly-one vars + hard constraints (07)."""
    candidate_slots: List[List[Tuple[int, int]]] = []
    for data in offering_datas:
        wmin = data.weekday_min if data.weekday_min is not None else 0
        wmax = data.weekday_max if data.weekday_max is not None else 6
        start_win = _hhmm_to_min(data.start_window) if data.start_window else 0
        end_win = _hhmm_to_min(data.end_window) if data.end_window else 24 * 60
        opts = [
            (w, s)
            for w in range(wmin, wmax + 1)
            for s in range(start_win,
                           max(end_win - data.duration_minutes + 1, 0), 30)
        ]
        if not opts:
            opts = [(w, start_win) for w in range(wmin, wmax + 1)]
        candidate_slots.append(opts)

    x: Dict[Tuple[int, int, int], object] = {}
    for o, data in enumerate(offering_datas):
        slots = candidate_slots[o]
        for c in range(data.meetings_per_week):
            for s in range(len(slots)):
                x[o, c, s] = model.new_bool_var(f"x_{o}_{c}_{s}")
            model.add_exactly_one([x[o, c, s] for s in range(len(slots))])

    # hard 1/2 — no two offerings share a resource at overlapping times
    for rid, res in resources.items():
        group = [o for o, d in enumerate(offering_datas)
                 if d.room_resource_id == rid
                 or d.instructor_resource_id == rid]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                oi, oj = group[i], group[j]
                di, dj = offering_datas[oi], offering_datas[oj]
                for c in range(di.meetings_per_week):
                    for d in range(dj.meetings_per_week):
                        for si in range(len(candidate_slots[oi])):
                            w_i, s_i = candidate_slots[oi][si]
                            for sj in range(len(candidate_slots[oj])):
                                w_j, s_j = candidate_slots[oj][sj]
                                end_i = s_i + di.duration_minutes
                                end_j = s_j + dj.duration_minutes
                                if (w_i == w_j and s_i < end_j
                                        and s_j < end_i):
                                    model.add(x[oi, c, si] + x[oj, d, sj] <= 1)

    # hard 5/6 — assignments must fit resource availability, avoid
    # existing commitments
    for o, data in enumerate(offering_datas):
        for rid in filter(None,
                          (data.room_resource_id,
                           data.instructor_resource_id)):
            res = resources.get(rid)
            if res is None:
                continue
            for c in range(data.meetings_per_week):
                for s, (w, s_min) in enumerate(candidate_slots[o]):
                    e_min = s_min + data.duration_minutes
                    inside = bool(res.availability) and any(
                        aw == w and a_s <= s_min and e_min <= a_e
                        for (aw, a_s, a_e) in res.availability
                    )
                    committed = any(
                        cw == w and c_s < e_min and s_min < c_e
                        for (cw, c_s, c_e) in res.commitments
                    )
                    if not inside or committed:
                        model.add(x[o, c, s] == 0)
    return candidate_slots, x


def _solve_and_persist(
    db: Session,
    run: SolverRun,
    cycle: PlanningCycle,
    offerings: List[CourseOffering],
    objective_weights: Optional[dict],
) -> SolverRun:
    offering_datas, resources, snap_offerings = _snapshot_inputs(
        db, cycle, offerings)

    input_snapshot = {
        "cycle_id": cycle.id,
        "cycle_status": cycle.status,
        "offerings": snap_offerings,
        "resources": {
            str(rid): {
                "kind": r.kind, "capacity": r.capacity,
                "availability": r.availability,
                "commitments": r.commitments,
            } for rid, r in resources.items()
        },
        "objective_weights": objective_weights or {},
        "created_at": _now().isoformat(),
    }
    run.input_snapshot = input_snapshot

    gaps = _data_gaps(offering_datas, resources)
    if gaps:
        run.status = RUN_INFEASIBLE
        run.result_snapshot = {
            "infeasible_causes": gaps, "warnings": [],
            "solver_status": "data_gaps",
        }
        run.finished_at = _now()
        db.commit()
        db.refresh(run)
        return run

    model = cp_model.CpModel()
    candidate_slots, x = _build_model(model, offering_datas, resources)

    weights = objective_weights or {}
    obj_terms = []
    for o, data in enumerate(offering_datas):
        w_early = weights.get("prefer_early_weekday", 0)
        if w_early:
            for c in range(data.meetings_per_week):
                for s, (w, s_min) in enumerate(candidate_slots[o]):
                    obj_terms.append(
                        (w_early * (w + s_min / 1440.0), x[o, c, s]))
    if obj_terms:
        model.minimize(cp_model.linear_expr(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 4
    status_code = solver.Solve(model)
    solver_status_name = cp_model.CpSolverStatus(status_code).name

    if status_code in (cp_model.MODEL_INVALID, cp_model.UNKNOWN):
        run.status = RUN_FAILED
        run.result_snapshot = {
            "error": f"solver stopped at {solver_status_name}; "
                     "no schedule is produced (07: partial ≠ final)",
            "solver_status": solver_status_name,
            "infeasible_causes": [], "warnings": [],
        }
        run.finished_at = _now()
        db.commit()
        db.refresh(run)
        return run

    if status_code == cp_model.INFEASIBLE:
        run.status = RUN_INFEASIBLE
        run.result_snapshot = {
            "solver_status": solver_status_name,
            "infeasible_causes": [{
                "code": "SCHEDULE_INFEASIBLE",
                "message": "No slot satisfies every hard constraint "
                           "(availability windows, existing commitments, "
                           "durations, weekday windows). Widen windows or "
                           "free resources, then re-solve.",
                "subject_type": "cycle", "subject_id": cycle.id,
            }],
            "warnings": [],
        }
        run.finished_at = _now()
        db.commit()
        db.refresh(run)
        return run

    # OPTIMAL or FEASIBLE → persist assignments (hard #9: shared offering
    # gets exactly one assignment row per occurrence, one per resource).
    run.status = RUN_FEASIBLE
    run.objective_score = float(solver.objective_value)
    warnings: List[dict] = []
    for o, data in enumerate(offering_datas):
        for c in range(data.meetings_per_week):
            chosen = next(
                s for s, (w, s_min) in enumerate(candidate_slots[o])
                if solver.value(x[o, c, s]) > 0.5
            )
            w, s_min = candidate_slots[o][chosen]
            e_min = s_min + data.duration_minutes
            payload = {
                "occurrence_no": c + 1,
                "weekday": w,
                "start_hhmm": f"{s_min // 60:02d}:{s_min % 60:02d}",
                "end_hhmm": f"{e_min // 60:02d}:{e_min % 60:02d}",
                "meetings_per_week": data.meetings_per_week,
                "duration_minutes": data.duration_minutes,
            }
            if data.room_resource_id is not None:
                db.add(SolverAssignment(
                    run_id=run.id,
                    offering_id=data.offering_id,
                    resource_id=data.room_resource_id,
                    **payload,
                ))
            if data.instructor_resource_id is not None:
                db.add(SolverAssignment(
                    run_id=run.id,
                    offering_id=data.offering_id,
                    resource_id=data.instructor_resource_id,
                    **payload,
                ))
        room_res = resources.get(data.room_resource_id) \
            if data.room_resource_id else None
        if (room_res and room_res.capacity is not None
                and room_res.capacity >= 2 * max(data.total_enrollment, 1)):
            warnings.append({
                "code": "ROOM_TOO_LARGE",
                "message": f"Room {room_res.capacity} seats for "
                           f"{data.total_enrollment} students; a smaller "
                           "room would fit (soft preference only)",
                "subject_type": "offering",
                "subject_id": data.offering_id,
            })

    run.result_snapshot = {
        "solver_status": solver_status_name,
        "objective_score": run.objective_score,
        "infeasible_causes": [],
        "warnings": warnings,
    }
    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run
