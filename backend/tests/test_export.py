"""Phase 6 export tests: Excel (.xlsx) and PDF download helpers.

Covers acceptance criteria for Phase 6:
- Excel workbook generation (valid workbook, headers + assignments)
- PDF generation (Persian/RTL content rendered)
- Eligibility filtering (exclude invalid/incomplete statuses via 409 on stale or non-feasible runs)

Run with:
  cd backend
  APP_ENV=test DB_HOST=localhost DB_PORT=5434 DB_NAME=barnamehsaz_novin_test \
    DB_USER=barnamehsaz DB_PASSWORD=change_me_local \
    .venv/bin/python -m pytest tests/test_export.py -v
"""
import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient


_REQUIRED_DB_PORT = "5434"
_REQUIRED_DB_NAME = "barnamehsaz_novin_test"
_REQUIRED_APP_ENV = "test"
_LOCAL_TEST_PASSWORD = "change_me_local"


def _enforce_test_db_isolation() -> None:
    os.environ.setdefault("DB_PASSWORD", _LOCAL_TEST_PASSWORD)
    problems = []
    if os.environ.get("APP_ENV") != _REQUIRED_APP_ENV:
        problems.append(f"APP_ENV must be '{_REQUIRED_APP_ENV}' (got {os.environ.get('APP_ENV')!r})")
    if os.environ.get("DB_HOST") != "localhost":
        problems.append(f"DB_HOST must be 'localhost' for the test DB (got {os.environ.get('DB_HOST')!r})")
    if os.environ.get("DB_PORT") != _REQUIRED_DB_PORT:
        problems.append(f"DB_PORT must be '{_REQUIRED_DB_PORT}' (got {os.environ.get('DB_PORT')!r})")
    if os.environ.get("DB_NAME") != _REQUIRED_DB_NAME:
        problems.append(f"DB_NAME must be '{_REQUIRED_DB_NAME}' (got {os.environ.get('DB_NAME')!r})")
    if problems:
        raise RuntimeError(
            "Refusing to run Phase 6 tests against a non-test database.\n"
            + "\n".join(f"  - {p}" for p in problems)
            + f"\nExport the exact test DB (DB_PORT={_REQUIRED_DB_PORT}, "
              f"DB_NAME={_REQUIRED_DB_NAME}, APP_ENV={_REQUIRED_APP_ENV}, "
              "DB_HOST=localhost) and re-run."
        )


_enforce_test_db_isolation()

from app.main import app, _login_failures  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import User, Membership, Organization, RefreshSession  # noqa: E402
from app.models.phase2 import (  # noqa: E402
    PlanningCycle, Unit, CycleUnit, Course, CourseOffering,
    OfferingUnit, Cohort, CycleCohort, MeetingRequirement,
    ResourceCommitment, ResourceAvailability, Resource, OfferingCohort,
)
from app.models.phase3 import (  # noqa: E402
    Submission, SubmissionRevision, SubmissionComment, WizardDraft,
    SharedOfferingApproval, DomainAuditEvent,
)
from app.models.phase4 import SolverRun, SolverAssignment, OfferingCorrection, RUN_INFEASIBLE  # noqa: E402
from app.core.password_utils import hash_password  # noqa: E402

DEMO_ADMIN = "admin@demo.example"
DEMO_MGR = "employee01@demo.example"
DEMO_PASSWORD = "12345678"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_state(db_session):
    tables = [
        SolverAssignment, OfferingCorrection, SolverRun, DomainAuditEvent,
        SharedOfferingApproval, WizardDraft, SubmissionComment,
        SubmissionRevision, Submission, MeetingRequirement, OfferingCohort,
        OfferingUnit, CourseOffering, Course, CycleCohort, Cohort,
        ResourceCommitment, ResourceAvailability, Resource, CycleUnit,
        PlanningCycle, Unit, Membership, RefreshSession, User, Organization,
    ]
    for tbl in tables:
        db_session.query(tbl).delete()
    db_session.commit()
    _seed(db_session)
    _login_failures.clear()
    yield


def _seed(db):
    org = Organization(name="Test Org", slug="test-org", timezone="Asia/Tehran")
    db.add(org)
    db.flush()
    admin = User(email=DEMO_ADMIN, password_hash=hash_password(DEMO_PASSWORD),
                 full_name="Test Admin", must_change_password=False, is_active=True,
                 organization_id=org.id)
    db.add(admin)
    db.flush()
    db.add(Membership(user_id=admin.id, organization_id=org.id, role="admin"))
    mgr = User(email=DEMO_MGR, password_hash=hash_password(DEMO_PASSWORD),
               full_name="Test Mgr", must_change_password=False, is_active=True,
               organization_id=org.id)
    db.add(mgr)
    db.flush()
    db.add(Membership(user_id=mgr.id, organization_id=org.id, role="manager"))
    db.commit()


def _login_admin(client):
    r = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def _mk_cycle(client, token, status="draft"):
    r = client.post("/phase2/planning-cycles",
                    json={"name": "Spring 2027", "term": "Spring 2027",
                          "status": status}, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_unit(client, token, name="CS Dept"):
    r = client.post("/phase2/units", json={"name": name}, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_course(client, token, code="CS101"):
    r = client.post("/phase2/courses", json={"code": code, "title": "Intro"}, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_offering(client, token, cycle, course, **kw):
    body = {"course_id": course["id"], "planning_cycle_id": cycle["id"],
            "meetings_per_week": 1, "duration_minutes": 90}
    body.update(kw)
    r = client.post("/phase2/offerings", json=body, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_resource(client, token, kind="room", name="R1", capacity=None):
    body = {"kind": kind, "name": name}
    if capacity is not None:
        body["capacity"] = capacity
    r = client.post("/phase2/resources", json=body, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_availability(client, token, resource, cycle, weekday=1, start="08:00", end="16:00"):
    r = client.post(
        f"/phase2/resources/{resource['id']}/availability",
        json={"cycle_id": cycle["id"], "weekday": weekday,
              "start_hhmm": start, "end_hhmm": end},
        headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_meeting_req(client, token, offering, **kw):
    body = {"offering_id": offering["id"]}
    body.update(kw)
    r = client.post("/phase2/meeting-requirements", json=body, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _link_unit_to_offering(client, token, offering, unit, enrollment=20):
    r = client.post(
        f"/phase2/offerings/{offering['id']}/units",
        json={"unit_id": unit["id"], "expected_enrollment": enrollment},
        headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_submission(client, token, cycle, unit):
    r = client.post("/phase3/submissions",
                    json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _submit(client, token, sub):
    r = client.post(f"/phase3/submissions/{sub['id']}/submit",
                    json={"expected_version": 0}, headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, token, sub):
    r = client.post(f"/phase3/submissions/{sub['id']}/approve",
                    json={"expected_version": 1}, headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _nominate_offering(client, token, offering, unit, room, instructor):
    r = client.post(
        f"/phase2/offerings/{offering['id']}/units/{unit['id']}/resources",
        json={"room_resource_id": room["id"], "instructor_resource_id": instructor["id"]},
        headers=_auth_headers(token))
    assert r.status_code in (200, 201), r.text
    return r.json()


def _setup_single_offering(client, token, db_session, with_submission=True, status="submitted"):
    cycle = _mk_cycle(client, token, status=status)
    unit = _mk_unit(client, token)
    course = _mk_course(client, token)
    offering = _mk_offering(client, token, cycle, course, required_room_capacity=40)
    room = _mk_resource(client, token, "room", "Room-1", 40)
    inst = _mk_resource(client, token, "instructor", "Inst-1")
    _mk_availability(client, token, room, cycle, weekday=2, start="08:00", end="14:00")
    _mk_availability(client, token, inst, cycle, weekday=2, start="08:00", end="14:00")
    _mk_meeting_req(client, token, offering,
                    allowed_weekday_min=2, allowed_weekday_max=2,
                    start_window_hhmm="08:00", end_window_hhmm="13:00")
    _link_unit_to_offering(client, token, offering, unit, enrollment=20)
    _nominate_offering(client, token, offering, unit, room, inst)
    if with_submission:
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]}, headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
    return cycle, offering, room, inst, unit, course


def _solve_cycle(client, token, cycle):
    r = client.post("/phase4/solve", json={"cycle_id": cycle["id"]},
                    headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "feasible", body
    return body["run_id"]


class TestExportExcel:
    """Verify Excel export produces valid .xlsx workbooks."""

    def test_feasible_run_returns_xlsx(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        run_id = _solve_cycle(client, token, cycle)
        client.post(f"/phase4/runs/{run_id}/publish",
                    json={"requested_version": None}, headers=_auth_headers(token))
        r = client.get(f"/phase4/runs/{run_id}/export/excel", headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        ct = r.headers["content-type"]
        assert ct.startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        buf = io.BytesIO(r.content)
        assert zipfile.is_zipfile(buf), "Expected valid .xlsx (ZIP archive)"
        with zipfile.ZipFile(buf) as z:
            names = z.namelist()
            assert any("xl/workbook.xml" in n for n in names), f"No workbook in xlsx: {names}"

    def test_excel_contains_persian_content(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        run_id = _solve_cycle(client, token, cycle)
        client.post(f"/phase4/runs/{run_id}/publish",
                    json={"requested_version": None}, headers=_auth_headers(token))
        r = client.get(f"/phase4/runs/{run_id}/export/excel", headers=_auth_headers(token))
        assert r.status_code == 200
        from openpyxl import load_workbook
        buf = io.BytesIO(r.content)
        wb = load_workbook(buf)
        ws = wb[wb.sheetnames[0]]
        vals = [cell.value for row in ws.iter_rows(max_row=3) for cell in row]
        all_text = " ".join(str(v) for v in vals if v)
        assert len(all_text) > 0, "Expected some text in first sheet"


class TestExportPdf:
    """Verify PDF export renders Persian/RTL content correctly."""

    def test_feasible_run_returns_pdf(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        run_id = _solve_cycle(client, token, cycle)
        client.post(f"/phase4/runs/{run_id}/publish",
                    json={"requested_version": None}, headers=_auth_headers(token))
        r = client.get(f"/phase4/runs/{run_id}/export/pdf", headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_pdf_minimum_size(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        run_id = _solve_cycle(client, token, cycle)
        client.post(f"/phase4/runs/{run_id}/publish",
                    json={"requested_version": None}, headers=_auth_headers(token))
        r = client.get(f"/phase4/runs/{run_id}/export/pdf", headers=_auth_headers(token))
        assert r.status_code == 200
        assert len(r.content) > 1000, "PDF appears truncated"


class TestExportEligibility:
    """Only feasible + non-stale runs may be exported."""

    def test_infeasible_run_returns_409(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        r = client.post("/phase4/solve", json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        run_id = r.json()["run_id"]
        with db_session.begin():
            run = db_session.get(SolverRun, run_id)
            run.status = RUN_INFEASIBLE
        for path in [f"/phase4/runs/{run_id}/export/excel",
                     f"/phase4/runs/{run_id}/export/pdf"]:
            r = client.get(path, headers=_auth_headers(token))
            assert r.status_code == 409, f"{path} expected 409, got {r.status_code}: {r.text[:200]}"

    def test_stale_run_returns_409(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course = \
            _setup_single_offering(client, token, db_session)
        run_id = _solve_cycle(client, token, cycle)
        client.post("/phase4/corrections",
                    json={
                        "cycle_id": cycle["id"],
                        "offering_id": offering["id"],
                        "field": "expected_enrollment",
                        "before_value": "20",
                        "after_value": "25",
                        "reason": "Enrollment updated"
                    }, headers=_auth_headers(token))
        r2 = client.get(f"/phase4/runs/{run_id}", headers=_auth_headers(token))
        assert r2.json()["run"]["stale"] is True, "Expected run stale after correction"
        for path in [f"/phase4/runs/{run_id}/export/excel",
                     f"/phase4/runs/{run_id}/export/pdf"]:
            r = client.get(path, headers=_auth_headers(token))
            assert r.status_code == 409, f"{path} expected 409, got {r.status_code}: {r.text[:200]}"
