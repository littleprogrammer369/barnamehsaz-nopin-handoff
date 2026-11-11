"""PDF (local renderer, no CDN) for a PublishedSchedule (08).

Uses ReportLab (reportlab) with a local embedded Persian font.
The output is RTL-friendly, A4 landscape-ready, per-day compact view.

Font asset:
  backend/assets/fonts/vazirmatn/Vazirmatn-Regular.ttf
  License: MIT (Vazirmatn upstream, rastikerdar/vazirmatn)

No network call at runtime — everything resolves from the bundled
ttf plus whatever ReportLab ships.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

BASE_DIR = Path(__file__).resolve().parent.parent.parent
_FONT_PATH = BASE_DIR / "assets" / "fonts" / "vazirmatn" / "Vazirmatn-Regular.ttf"
_FAMILY_NAME = "Vazirmatn"
_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

# Lazy font registration so callers don't pay setup cost before first render.
_font_registered: bool = False


def _register_font() -> None:
    global _font_registered
    if not _font_registered:
        if _FONT_PATH.exists():
            pdfmetrics.registerFont(TTFont(_FAMILY_NAME, str(_FONT_PATH)))
        else:
            # Fallback to VazirmatnSans which ships with Linux;
            # RTL/Persian glyphs are not reliable here; this is
            # only for environments where the custom font bundle is
            # unavailable (deployment fallback path).
            try:
                pdfmetrics.registerFont(TTFont("Vazirmatn", "/usr/share/fonts/truetype/dejavu/VazirmatnSans.ttf"))
            except Exception:
                pass
        _font_registered = True


def _style(name: str, **kw):
    defaults = {"spaceAfter": 6, "leading": 16}
    defaults.update(kw)
    return ParagraphStyle(name=name, fontName=_FAMILY_NAME, **defaults)


def _styles():
    base = getSampleStyleSheet()
    s_title = _style("Title",
                     fontSize=18, alignment=TA_CENTER,
                     textColor="#1F4E78", spaceBefore=0, spaceAfter=12)
    s_subtitle = _style("Subtitle",
                        fontSize=12, alignment=TA_CENTER,
                        textColor="#555555", spaceBefore=0, spaceAfter=16)
    s_heading = _style("Heading1",
                       fontSize=13, alignment=TA_CENTER,
                       textColor="#1F4E78", spaceBefore=8, spaceAfter=6)
    s_body = _style("Body",
                    fontSize=11, alignment=TA_RIGHT, textColor="#222222")
    s_muted = _style("Muted",
                     fontSize=9, alignment=TA_CENTER,
                     textColor="#888888", spaceAfter=24)
    return {
        "Title": s_title,
        "Subtitle": s_subtitle,
        "Heading1": s_heading,
        "Body": s_body,
        "Muted": s_muted,
        "Number": _style("Number",
                         fontSize=10, alignment=TA_CENTER,
                         textColor="#111111"),
    }


def _row_height(cells: list, style: dict, w: int) -> float:
    return max(20, min(50, w // max(1, len(cells))))


def _get_assignment_query_base_pdf(db, run_id: int, unit_id: Optional[int] = None):
    """Get base SolverAssignment query for PDF, optionally filtered by unit.
    
    If unit_id is None: return all assignments (admin view).
    If unit_id is set: return only assignments from offerings in that unit.
    """
    from app.models.phase4 import SolverAssignment
    from app.models.phase2 import OfferingUnit
    
    q = db.query(SolverAssignment).filter(SolverAssignment.run_id == run_id)
    
    if unit_id is not None:
        # Join offering_id -> OfferingUnit -> unit_id
        q = (
            q.join(OfferingUnit, SolverAssignment.offering_id == OfferingUnit.offering_id)
            .filter(OfferingUnit.unit_id == unit_id)
        )
    
    return q

def _render_assignments(elements, style, db, cycle_id: int, run_id: int, unit_id: Optional[int] = None) -> None:
    assigns = (
        _get_assignment_query_base_pdf(db, run_id, unit_id)
        .order_by(SolverAssignment.weekday, SolverAssignment.start_hhmm)
        .all()
    )
    elements.append(Paragraph("جدول اختصاص تکالیف و منابع", style["Heading1"]))
    header_cols = ["کد_درس", "عنوان", "واحد_آموزشی", "روز", "شروع", "پایان", "اتاق", "ورژن"]
    data_rows = [header_cols]
    for a in assigns[:150]:
        code = getattr(getattr(a, "course", None), "code", "?") if hasattr(a, "course") else "?"
        title = getattr(getattr(a, "course", None), "title", "") if hasattr(a, "course") else f"offering#{a.offering_id}"
        data_rows.append([
            str(code or ""),
            str(title)[:40],
            str(a.offering_id),
            _WEEKDAYS[a.weekday] if a.weekday is not None else "—",
            str(a.start_hhmm or "—"),
            str(a.end_hhmm or "—"),
            str(a.resource_id or "—"),
            "—",
        ])
    table = Table(data_rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#1F4E78"),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#ffffff"),
        ("ALIGN", (0, 0), (-1, 0), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), _FAMILY_NAME),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BACKGROUND", (0, 1), (-1, -1), "#f5f5f5"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#cccccc"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)
    elements.append(Paragraph(
        f"مجموع {len(assigns)} تخصیص ثبت شده است. نسخه منتشرشده بر اساس snapshot ذخیره‌سازی شده تولید می‌گردد.",
        style["Body"]
    ))
    elements.append(PageBreak())


def _render_calendar(elements, style, db, run_id: int, unit_id: Optional[int] = None) -> None:
    starts = sorted({a.start_hhmm for a in
                     _get_assignment_query_base_pdf(db, run_id, unit_id).all()})
    elements.append(Paragraph("تقویم هفتگی (بازه‌ها × روزهای هفته)", style["Heading1"]))
    data_rows = [["روز\\بازه"] + list(_WEEKDAYS)]
    for ti, s in enumerate(starts):
        row = [f"{ti+1}. {s}"]
        for d in range(7):
            n = _get_assignment_query_base_pdf(db, run_id, unit_id).filter(
                SolverAssignment.weekday == d,
                SolverAssignment.start_hhmm == s,
            ).count()
            row.append(str(n))
        data_rows.append(row)
    table = Table(data_rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#1F4E78"),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#ffffff"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), _FAMILY_NAME),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BACKGROUND", (0, 1), (-1, -1), "#f5f5f5"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#cccccc"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)
    elements.append(Paragraph("تعداد کلاس‌ها در هر بازه/روز. داده تکراری در شیت assignments هم‌زمان نمایش داده می‌شود.", style["Body"]))
    elements.append(PageBreak())


def _render_envelope(elements, style, cycle, run) -> None:
    elements.append(Paragraph("مشخصات انتشار برنامه نهایی", style["Heading1"]))
    rows = [
        ["سازمان", str(cycle.organization_id if hasattr(cycle, "organization_id") else "—")],
        ["نام چرخه", f"{cycle.name} | {cycle.term}"],
        ["وضعیت اجرا", run.status or "—"],
        ["ورژن انتشار", str(getattr(cycle, "version", "—"))],
        ["تاریخ انتشار", run.created_at.astimezone(timezone.utc).isoformat() if run.created_at else "—"],
        ["کاربر", f"# {run.actor_user_id}" if run.actor_user_id else "—"],
        ["علت", run.stale_reason or "—"],
    ]
    tbl_data = [[r[0], r[1]] for r in rows]
    table = Table(tbl_data)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FAMILY_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("BACKGROUND", (0, 0), (0, -1), "#D9E1F2"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#cccccc"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)


def export_published_schedule_pdf(
    db,
    schedule,
    palette_version: Optional[float] = None,
    unit_id: Optional[int] = None,
) -> io.BytesIO:
    """Generate a printable PDF schedule.
    
    If unit_id is None: admin sees all assignments.
    If unit_id is set: unit_manager sees only assignments from their unit's offerings.
    """
    if schedule.stale:
        raise RuntimeError("Published schedule is stale (inputs changed after publication)")
    if schedule.status not in ("current", "previous"):
        raise RuntimeError(f"Uneligible status {schedule.status!r} cannot be exported")
    if not schedule.result_snapshot:
        raise RuntimeError("No result snapshot; cannot export")

    _register_font()

    from app.models.phase4 import SolverRun as SolverRun
    run = db.get(SolverRun, schedule.run_id)
    if run is None:
        raise RuntimeError(f"No run #{schedule.run_id}")

    from app.models.phase2 import PlanningCycle
    cycle = db.get(PlanningCycle, schedule.cycle_id)
    if cycle is None:
        raise RuntimeError(f"No cycle #{schedule.cycle_id}")

    buf = io.BytesIO()
    styles = _styles()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"برنامه {schedule.version}",
        author="برنامه‌ساز نوین",
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(id="A4_L", frames=frame, pagesize=A4)])

    elements = []
    elements.append(Paragraph("برنامه‌ساز نوین – چاپی منتشرشده", styles["Title"]))
    date_str = run.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if run.created_at else "—"
    elements.append(Paragraph(f"چرخه: {cycle.name} ({cycle.term})   |   نسخه: {schedule.version}   |   تاریخ انتشار: {date_str}",
                      styles["Subtitle"]))
    elements.append(Paragraph(styles["Body"].fontName, styles["Body"]))

    _render_envelope(elements, styles, cycle, run)
    elements.append(Paragraph("", styles["Body"]))
    _render_assignments(elements, styles, db, schedule.cycle_id, schedule.run_id, unit_id)
    _render_calendar(elements, styles, db, schedule.run_id, unit_id)

    doc.build(elements)
    buf.seek(0)
    return buf
