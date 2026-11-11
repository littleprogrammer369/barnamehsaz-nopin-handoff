"""Excel (XLSX) export for a PublishedSchedule (08).

Workbook layout (08):
  0. _legend               - readme / how to read
  1. assignments            - course.section x occurrence x room (primary grid)
  2. calendar               - weekday x time grid (zone view)
  3. cohort                 - cohort x expected_enrollment
  4. instructor             - instructor assignment
  5. room                   - room capacity
  6. version                - publication envelope

Rules (08):
  - Shared data printed once; no wrong duplication.
  - Freeze panes + header styling + column widths on every sheet.
  - Invalid status or missing result snapshot raises ExportError.
"""
from __future__ import annotations

import io
from datetime import datetime, tzinfo, timezone
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models.phase2 import CourseOffering, Course, CycleCohort, PlanningCycle, OfferingUnit
from app.models.phase4 import SolverRun, PublishedSchedule, SolverAssignment

_RTL = "\u200f"

_HEADER_FONT = Font(name="Vazirmatn", bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_TITLE_FONT = Font(name="Vazirmatn", bold=True, size=14, color="1F4E78")
_NORMAL_FONT = Font(name="Vazirmatn", size=11)
_BORDER = Border(
    left=Side("thin"), right=Side("thin"),
    top=Side("thin"), bottom=Side("thin"),
)
_RTL_ALIGN = Alignment(horizontal="right", vertical="center", wrap_text=True)
_LTR_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)


def _get_assignment_query_base(db, run_id: int, unit_id: Optional[int] = None):
    """Get base SolverAssignment query, optionally filtered by unit.
    
    If unit_id is None: return all assignments (admin view).
    If unit_id is set: return only assignments from offerings in that unit.
    """
    q = db.query(SolverAssignment).filter(SolverAssignment.run_id == run_id)
    
    if unit_id is not None:
        # Join offering_id -> OfferingUnit -> unit_id
        q = (
            q.join(OfferingUnit, SolverAssignment.offering_id == OfferingUnit.offering_id)
            .filter(OfferingUnit.unit_id == unit_id)
        )
    
    return q



def _rname(s: str) -> str:
    return _RTL + s


def _style_header(ws, ncols: int, row: int = 1) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _RTL_ALIGN


def _widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _fetch_run(db, schedule: PublishedSchedule) -> SolverRun:
    if schedule.source_run_id:
        return db.get(SolverRun, schedule.source_run_id)
    return db.get(SolverRun, schedule.run_id)


def _course_for(db, offering_id: int):
    off = db.get(CourseOffering, offering_id)
    if off is None or off.course is None:
        raise RuntimeError(f"Offering {offering_id} has no course")
    return off.course


def _build_legend(wb: Workbook, cycle, run: SolverRun, version: float) -> None:
    ws = wb.create_sheet("_legend")
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:C1")
    c = ws["A1"]
    c.value = "برنامه‌ساز نوین - چاپی منتشرشده - Legend"
    c.font = _TITLE_FONT
    c.alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[1].height = 30

    props = [
        ("Cycle", f"{cycle.name} | {cycle.term}"),
        ("Version", str(version)),
        ("Published_at", run.created_at.astimezone(timezone.utc).isoformat() if run.created_at else "—"),
        ("Source_Run", f"#{run.id} ({run.status})"),
        ("Actor", f"#{run.actor_user_id}" if run.actor_user_id else "—"),
        ("Rows", "course.section x occurrence x room"),
        ("Invalid", "run.status != 'feasible' -> export fails"),
    ]
    ws.append(["Property", "Value", "Note"])
    for label, val in props:
        ws.append([label, val, ""])

    _style_header(ws, 3)
    _widths(ws, [20, 80, 30])
    ws.freeze_panes = "A2"


def _build_assignments(ws, db, cycle_id: int, run_id: int, version: float, unit_id: Optional[int] = None) -> None:
    ws.sheet_view.showGridLines = False
    header = [_rname("Code"), _rname("Title"), _rname("Offering"),
              _rname("Weekday"), _rname("Start"), _rname("End"),
              _rname("Room"), _rname("Was Shared"), _rname("Version")]
    ws.append(header)
    _style_header(ws, len(header))

    assigns = _get_assignment_query_base(db, run_id, unit_id).order_by(
        SolverAssignment.weekday, SolverAssignment.start_hhmm
    ).all()
    for a in assigns:
        try:
            course = _course_for(db, a.offering_id)
            code, title = course.code, course.title
        except Exception:
            code, title = "?", f"offering #{a.offering_id}"
        ws.append([
            code, title, a.offering_id,
            a.weekday, a.start_hhmm, a.end_hhmm,
            a.resource_id if a.resource_id else "—",
            "YES" if a.occurrence_no > 1 else "NO",
            version,
        ])

    for c in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 18
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{ws.max_row}"


def _build_calendar(ws, db, run_id: int, unit_id: Optional[int] = None) -> None:
    ws.sheet_view.showGridLines = False
    weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    header = [_rname("Day_Index")] + [_rname(d) for d in weekdays]
    ws.append(header)
    _style_header(ws, len(header))

    starts = sorted({a.start_hhmm for a in
                     _get_assignment_query_base(db, run_id, unit_id).all()})
    for ti, s in enumerate(starts):
        row = [f"{ti+1}. {s}"]
        for d in range(7):
            n = _get_assignment_query_base(db, run_id, unit_id).filter(
                SolverAssignment.weekday == d,
                SolverAssignment.start_hhmm == s,
            ).count()
            row.append(n)
        ws.append(row)

    for c in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 16
    ws.freeze_panes = "B2"


def _build_cohort(ws, db, cycle_id: int) -> None:
    ws.sheet_view.showGridLines = False
    header = [_rname("Cohort"), _rname("Unit"), _rname("Expected_Enrollment")]
    ws.append(header)
    _style_header(ws, len(header))

    for cc in db.query(CycleCohort).filter(CycleCohort.cycle_id == cycle_id).all():
        ws.append([cc.cohort.name or "", cc.cohort.unit.name if cc.cohort.unit else "", cc.expected_enrollment])

    for c in range(1, 4):
        ws.column_dimensions[get_column_letter(c)].width = 20
    ws.freeze_panes = "A2"


def _build_instructor(ws, db, run_id: int, version: float, unit_id: Optional[int] = None) -> None:
    ws.sheet_view.showGridLines = False
    header = [_rname("Offering"), _rname("Resource"), _rname("Weekday"), _rname("Start"), _rname("End"), _rname("Version")]
    ws.append(header)
    _style_header(ws, len(header))

    for a in _get_assignment_query_base(db, run_id, unit_id).all():
        ws.append([a.offering_id, a.resource_id or "—", a.weekday, a.start_hhmm, a.end_hhmm, version])

    for c in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 18
    ws.freeze_panes = "A2"


def _build_room(ws, db, run_id: int, version: float, unit_id: Optional[int] = None) -> None:
    ws.sheet_view.showGridLines = False
    header = [_rname("Room"), _rname("Capacity"), _rname("Version")]
    ws.append(header)
    _style_header(ws, len(header))

    for a in _get_assignment_query_base(db, run_id, unit_id).all():
        ws.append([a.resource_id or "—", "—", version])

    for c in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 20
    ws.freeze_panes = "A2"


def _build_version(ws, cycle, run: SolverRun) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:B1")
    c = ws["A1"]
    c.value = "نشان‌گروهی انتشار (Envelope)"
    c.font = _TITLE_FONT
    c.alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[1].height = 28

    rows = [
        ("Cycle", f"{cycle.name} ({cycle.term})"),
        ("Version", str(cycle and getattr(cycle, 'version', '—'))),
        ("Status", run.status),
        ("Published_at", run.created_at.astimezone(timezone.utc).isoformat() if run.created_at else "—"),
        ("Source_Run_ID", run.id),
        ("Actor", f"#{run.actor_user_id}" if run.actor_user_id else "—"),
    ]
    for label, val in rows:
        ws.append([label, val])
    _widths(ws, [24, 80])


def export_published_schedule_xlsx(
    db,
    schedule: PublishedSchedule,
    unit_id: Optional[int] = None,
) -> io.BytesIO:
    """Return an in-memory .xlsx for the published schedule.
    
    If unit_id is None: admin sees all assignments.
    If unit_id is set: unit_manager sees only assignments from their unit's offerings.
    """
    if schedule.stale:
        raise RuntimeError("Published schedule is stale (inputs changed after publication)")
    if schedule.status not in ("current", "previous"):
        raise RuntimeError(f"Uneligible status {schedule.status!r} cannot be exported")
    if not schedule.result_snapshot:
        raise RuntimeError("No result snapshot; cannot export")

    run = _fetch_run(db, schedule)
    if run is None:
        raise RuntimeError(f"No run #{schedule.run_id}")

    cycle = db.get(PlanningCycle, schedule.cycle_id)
    if cycle is None:
        raise RuntimeError(f"No cycle #{schedule.cycle_id}")

    wb = Workbook()
    wb.remove(wb.active)

    _build_legend(wb, cycle, run, schedule.version)
    ws1 = wb.create_sheet("assignments")
    _build_assignments(ws1, db, schedule.cycle_id, schedule.run_id, schedule.version, unit_id)
    ws2 = wb.create_sheet("calendar")
    _build_calendar(ws2, db, schedule.run_id, unit_id)
    ws3 = wb.create_sheet("cohort")
    _build_cohort(ws3, db, schedule.cycle_id)
    ws4 = wb.create_sheet("instructor")
    _build_instructor(ws4, db, schedule.run_id, schedule.version, unit_id)
    ws5 = wb.create_sheet("room")
    _build_room(ws5, db, schedule.run_id, schedule.version, unit_id)
    ws6 = wb.create_sheet("version")
    _build_version(ws6, cycle, run)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
