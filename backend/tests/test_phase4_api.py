"""Phase 4 integration tests: global preflight, OR-Tools CP-SAT solver,
run history / comparison, and the manager correction track.

Covers:
- preflight blocker codes: CYCLE_NOT_SOLVABLE, MEETING_REQUIREMENT_MISSING,
  Q12_RESOURCES_NOT_NOMINATED, ENROLLMENT_EXCEEDS_ROOM_CAPACITY,
  SUBMISSION_MISSING / SUBMISSION_NOT_APPROVED
- solver terminal states: feasible (assignments + immutable snapshots),
  infeasible (data gaps), partial results never exposed as final
- run immutability: history listing, single-run snapshots, comparison
- corrections: append-only, approvals + runs stale-marked atomically
- Q12 nomination endpoint: single-resource identity, 409 on conflict

Run with:
  cd backend
  APP_ENV=test DB_HOST=localhost DB_PORT=5434 DB_NAME=barnamehsaz_novin_test \
    DB_USER=barnamehsaz DB_PASSWORD=change_me_local \
    .venv/bin/python -m pytest tests/test_phase4_api.py -v
"""
import os
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test-only DB isolation guard (fail-fast, before any app/engine import).
#
# These tests must NEVER touch the development database. ``app.database``
# builds the SQLAlchemy engine at import time from ``Settings`` (defaults:
# port 5433 / ``barnamehsaz_novin_dev``), so a careless shell env can point
# the whole suite at dev. The ``clean_state`` fixture then mass-deletes rows,
# which would be catastrophic on a non-test DB.
#
# We therefore *validate* the effective env before importing anything from
# ``app``: the critical identity values (APP_ENV / DB_HOST / DB_PORT /
# DB_NAME) must already equal the test database, or collection aborts with
# a clear ``RuntimeError``. Only the DB password gets a local ``setdefault``
# fallback so the suite is reproducible on a fresh checkout. No
# reset/drop/truncate is performed here — this is a configuration gate only.
# ---------------------------------------------------------------------------

_REQUIRED_DB_PORT = "5434"
_REQUIRED_DB_NAME = "barnamehsaz_novin_test"
_REQUIRED_APP_ENV = "test"
_LOCAL_TEST_PASSWORD = "change_me_local"


def _resolve_test_db_password() -> str:
    """Password from the local environment, with a documented fallback.

    ``setdefault`` here is intentional: if the operator exported
    ``DB_PASSWORD`` they keep control, otherwise we use the local test
    credential so the suite is reproducible on a fresh checkout.
    """
    os.environ.setdefault("DB_PASSWORD", _LOCAL_TEST_PASSWORD)
    return os.environ["DB_PASSWORD"]


def _enforce_test_db_isolation() -> None:
    """Validate the effective test-DB configuration; fail fast on mismatch.

    Runs before importing any ``app`` module so the SQLAlchemy engine is
    never built against the wrong database. We do NOT overwrite the
    operator's shell env — we read it, and if the critical values are not
    exactly the test database, we raise ``RuntimeError`` and abort
    collection. Only the DB_PASSWORD gets a local default (setdefault) so
    the suite remains reproducible on a fresh checkout.

    This is the opposite of ``setdefault`` for the identity fields: if the
    shell already exported ``DB_NAME=barnamehsaz_novin_dev`` we must stop,
    not silently rewrite it.
    """
    # Password comes from the local environment; fall back to the documented
    # test credential only when unset.
    _resolve_test_db_password()

    problems = []
    if os.environ.get("APP_ENV") != _REQUIRED_APP_ENV:
        problems.append(
            f"APP_ENV must be '{_REQUIRED_APP_ENV}' "
            f"(got {os.environ.get('APP_ENV')!r})"
        )
    if os.environ.get("DB_HOST") != "localhost":
        problems.append(
            f"DB_HOST must be 'localhost' for the test DB "
            f"(got {os.environ.get('DB_HOST')!r})"
        )
    if os.environ.get("DB_PORT") != _REQUIRED_DB_PORT:
        problems.append(
            f"DB_PORT must be '{_REQUIRED_DB_PORT}' "
            f"(got {os.environ.get('DB_PORT')!r})"
        )
    if os.environ.get("DB_NAME") != _REQUIRED_DB_NAME:
        problems.append(
            f"DB_NAME must be '{_REQUIRED_DB_NAME}' "
            f"(got {os.environ.get('DB_NAME')!r})"
        )

    if problems:
        raise RuntimeError(
            "Refusing to run Phase 4 tests against a non-test database.\n"
            + "\n".join(f"  - {p}" for p in problems)
            + f"\nExport the exact test DB (DB_PORT={_REQUIRED_DB_PORT}, "
              f"DB_NAME={_REQUIRED_DB_NAME}, APP_ENV={_REQUIRED_APP_ENV}, "
            "DB_HOST=localhost) and re-run. See the module docstring for the "
            "canonical command. No reset/drop/truncate is performed here — "
            "this is a configuration gate only."
        )


# Import-time gate: must run before ``from app.main import ...`` below.
_enforce_test_db_isolation()

from app.main import app, _login_failures  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import (  # noqa: E402
    User, Membership, Organization, RefreshSession,
)
from app.models.phase2 import (  # noqa: E402
    PlanningCycle, Unit, CycleUnit, Course, CourseOffering,
    OfferingUnit, Cohort, CycleCohort, MeetingRequirement,
    ResourceCommitment, ResourceAvailability, Resource, OfferingCohort,
)
from app.models.phase3 import (  # noqa: E402
    Submission, SubmissionRevision, SubmissionComment, WizardDraft,
    SharedOfferingApproval, DomainAuditEvent,
)
from app.models.phase4 import (  # noqa: E402
    SolverRun, SolverAssignment, OfferingCorrection,
    RUN_FEASIBLE, RUN_INFEASIBLE,
)
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
    db_session.query(SolverAssignment).delete()
    db_session.query(OfferingCorrection).delete()
    db_session.query(SolverRun).delete()
    db_session.query(DomainAuditEvent).delete()
    db_session.query(SharedOfferingApproval).delete()
    db_session.query(WizardDraft).delete()
    db_session.query(SubmissionComment).delete()
    db_session.query(SubmissionRevision).delete()
    db_session.query(Submission).delete()
    db_session.query(MeetingRequirement).delete()
    db_session.query(OfferingCohort).delete()
    db_session.query(OfferingUnit).delete()
    db_session.query(CourseOffering).delete()
    db_session.query(Course).delete()
    db_session.query(CycleCohort).delete()
    db_session.query(Cohort).delete()
    db_session.query(ResourceCommitment).delete()
    db_session.query(ResourceAvailability).delete()
    db_session.query(Resource).delete()
    db_session.query(CycleUnit).delete()
    db_session.query(PlanningCycle).delete()
    db_session.query(Unit).delete()
    db_session.query(Membership).delete()
    db_session.query(RefreshSession).delete()
    db_session.query(User).delete()
    db_session.query(Organization).delete()
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
    db.add(Membership(user_id=mgr.id, organization_id=org.id, role="unit_manager"))
    db.commit()


def _login_admin(client):
    r = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- helpers
def _mk_cycle(client, token, status="draft"):
    r = client.post("/phase2/planning-cycles",
                    json={"name": "Spring 2027", "term": "Spring 2027",
                          "status": status},
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_unit(client, token, name="CS Dept"):
    r = client.post("/phase2/units", json={"name": name},
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_course(client, token, code="CS101"):
    r = client.post("/phase2/courses", json={"code": code, "title": "Intro"},
                    headers=_auth_headers(token))
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
    r = client.post("/phase2/resources", json=body,
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _mk_availability(client, token, resource, cycle, weekday=1,
                      start="08:00", end="16:00"):
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
    r = client.post("/phase2/meeting-requirements", json=body,
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _link_unit_to_offering(client, token, offering, unit, enrollment=20):
    r = client.post(
        f"/phase2/offerings/{offering['id']}/units",
        json={"unit_id": unit["id"], "expected_enrollment": enrollment},
        headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _nominate(client, token, offering, unit, room=None, instructor=None):
    r = client.post(
        f"/phase2/offerings/{offering['id']}/units/{unit['id']}/resources",
        json={"room_resource_id": room, "instructor_resource_id": instructor},
        headers=_auth_headers(token))
    assert r.status_code in (200, 409, 404), r.text
    return r


def _mk_submission(client, token, cycle, unit):
    r = client.post("/phase3/submissions",
                    json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                    headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()


def _submit(client, token, sub):
    r = client.post(f"/phase3/submissions/{sub['id']}/submit",
                    json={"expected_version": 0},
                    headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, token, sub):
    r = client.post(f"/phase3/submissions/{sub['id']}/approve",
                    json={"expected_version": 1},
                    headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()

def _setup_single_offering(client, token, db_session, with_submission=True,
                            status="submitted"):
    """Build a minimal solvable single-unit offering cycle.

    Returns (cycle, offering, room, instructor, unit, course, link)."""
    cycle = _mk_cycle(client, token, status=status)
    unit = _mk_unit(client, token)
    course = _mk_course(client, token)
    offering = _mk_offering(client, token, cycle, course,
                             required_room_capacity=40)
    room = _mk_resource(client, token, "room", "Room-1", 40)
    inst = _mk_resource(client, token, "instructor", "Inst-1")
    _mk_availability(client, token, room, cycle, weekday=2,
                     start="08:00", end="14:00")
    _mk_availability(client, token, inst, cycle, weekday=2,
                     start="08:00", end="14:00")
    _mk_meeting_req(client, token, offering,
                    allowed_weekday_min=2, allowed_weekday_max=2,
                    start_window_hhmm="08:00", end_window_hhmm="13:00")
    link = _link_unit_to_offering(client, token, offering, unit, enrollment=20)
    if with_submission:
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
    return cycle, offering, room, inst, unit, course, link


def _nominate_offering(client, token, offering, unit, room, instructor):
    _nominate(client, token, offering, unit,
              room=room["id"], instructor=instructor["id"])


def _record_shared_approval(client, token, offering, unit,
                            status="unit_approved"):
    """Create/record a real SharedOfferingApproval via the legit API path.

    POST /phase3/offerings/{id}/shared-approvals — the unit must already
    participate in the offering (see _link_unit_to_offering). Returns the
    approval read object (201).
    """
    r = client.post(
        f"/phase3/offerings/{offering['id']}/shared-approvals",
        json={"unit_id": unit["id"], "status": status},
        headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()




class TestPreflightBlockers:
    """07 پیش‌شرط: every blocker prevents the solve; each has a code and
    an actionable message."""

    def test_draft_cycle_blocked(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course, link = \
            _setup_single_offering(client, token, db_session,
                                    status="draft")
        _nominate_offering(client, token, offering, unit, room, inst)
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        codes = [b["code"] for b in detail["blockers"]]
        assert "CYCLE_NOT_SOLVABLE" in codes

    def test_missing_meeting_requirement(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course, link = \
            _setup_single_offering(client, token, db_session)
        db_session.query(MeetingRequirement).filter(
            MeetingRequirement.offering_id == offering["id"]).delete()
        db_session.commit()
        _nominate_offering(client, token, offering, unit, room, inst)
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 409, r.text
        codes = [b["code"] for b in r.json()["detail"]["blockers"]]
        assert "MEETING_REQUIREMENT_MISSING" in codes

    def test_q12_not_nominated(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course, link = \
            _setup_single_offering(client, token, db_session)
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 409, r.text
        codes = [b["code"] for b in r.json()["detail"]["blockers"]]
        assert "Q12_RESOURCES_NOT_NOMINATED" in codes

    def test_unapproved_submission_blocked(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering = _mk_offering(client, token, cycle, course)
        _link_unit_to_offering(client, token, offering, unit)
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        _submit(client, token, sub)  # stays SUB_SUBMITTED, not approved
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 409, r.text
        codes = [b["code"] for b in r.json()["detail"]["blockers"]]
        assert "SUBMISSION_NOT_APPROVED" in codes


class TestSolverFeasible:
    """07 حل قابل‌تصدیق: valid cycle → feasible run with assignments and
    an immutable input snapshot."""

    def test_feasible_run(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course, link = \
            _setup_single_offering(client, token, db_session)
        _nominate_offering(client, token, offering, unit, room, inst)
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "feasible", body
        assert body["can_publish"] is True
        run_id = body["run_id"]

        d = client.get(f"/phase4/runs/{run_id}",
                       headers=_auth_headers(token)).json()
        snap = d["input_snapshot"]
        assert snap is not None
        assert snap["cycle_id"] == cycle["id"]
        assert len(d["assignments"]) >= 1
        for a in d["assignments"]:
            assert a["weekday"] == 2
            assert a["resource_id"] in (room["id"], inst["id"])

    def test_run_history_and_compare(self, client, db_session):
        token = _login_admin(client)["access_token"]
        cycle, offering, room, inst, unit, course, link = \
            _setup_single_offering(client, token, db_session)
        _nominate_offering(client, token, offering, unit, room, inst)
        r1 = client.post("/phase4/solve",
                         json={"cycle_id": cycle["id"]},
                         headers=_auth_headers(token)).json()
        r2 = client.post("/phase4/solve",
                         json={"cycle_id": cycle["id"]},
                         headers=_auth_headers(token)).json()
        assert r1["run_id"] != r2["run_id"]

        runs = client.get(f"/phase4/runs?cycle_id={cycle['id']}",
                          headers=_auth_headers(token)).json()
        assert len(runs) == 2
        assert runs[0]["id"] == r2["run_id"]  # newest first

        comp_resp = client.get(
            f"/phase4/runs/compare?a={r1['run_id']}&b={r2['run_id']}",
            headers=_auth_headers(token))
        assert comp_resp.status_code == 200, comp_resp.text
        comp = comp_resp.json()
        assert comp["a"]["status"] == "feasible"
        assert comp["b"]["status"] == "feasible"
        assert comp["score_delta"] == 0.0




class TestSolverInfeasible:
    """08 Inferrable solver scenarios: infeasible constraints.

    These tests verify that when the solver cannot find a valid schedule
    (e.g. conflicting resource windows, insufficient capacity, missing
    nominations), the run correctly terminates in the INFEASIBLE terminal
    state and no partial results are exposed as final.
    """

    def test_infeasible_capacity_gap(self, client, db_session):
        """Capacity shortfall is a pre-solver *data gap*, not an OR-Tools run.

        A single offering whose required_room_capacity (999) exceeds every
        nominated room's capacity (40) makes ``_data_gaps`` emit
        ENROLLMENT_EXCEEDS_ROOM_CAPACITY *before* the OR-Tools model is built.
        The run therefore terminates as infeasible with the documented
        ``data_gaps`` contract value in ``result_snapshot.solver_status`` —
        NOT a CpSolverStatus. This test is strictly the capacity/data-gap path
        and must not be conflated with the real OR-Tools-infeasible test
        (``test_infeasible_solver_capacity_vs_meeting`` below).
        """
        from app.models.phase4 import RUN_INFEASIBLE
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering = _mk_offering(client, token, cycle, course,
                               required_room_capacity=999)
        room = _mk_resource(client, token, "room", "Room-1", 40)
        inst = _mk_resource(client, token, "instructor", "Inst-1")
        _mk_availability(client, token, room, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_availability(client, token, inst, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_meeting_req(client, token, offering,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="13:00")
        link = _link_unit_to_offering(client, token, offering, unit,
                                      enrollment=20)
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
        _nominate_offering(client, token, offering, unit, room, inst)
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "infeasible", body
        assert body["objective_score"] is None
        assert len(body["infeasible_causes"]) > 0
        run_id = body["run_id"]
        # Verify the run is terminal (not feasible, can_publish is False)
        assert body["can_publish"] is False
        # Check run detail has immutable snapshot + infeasible result
        d = client.get(f"/phase4/runs/{run_id}",
                       headers=_auth_headers(token)).json()
        snap = d["input_snapshot"]
        assert snap is not None
        assert snap["cycle_id"] == cycle["id"]
        assert len(d["assignments"]) == 0
        codes = [b["code"] for b in body["infeasible_causes"]]
        # Should mention capacity or availability
        assert any('capacity' in c.lower() or 'availability' in c.lower()
                   for c in codes)
        # solver_status contract: infeasible runs carry solver_status in the
        # result snapshot. Missing-room / capacity scenarios produce a
        # 'data_gaps' marker, OR-Tools-driven infeasible runs produce the
        # CpSolverStatus name ('INFEASIBLE', 'INFEASIBLE_OR_UNSATISFIABLE').
        # No ad-hoc status values (07 output contract).
        assert "solver_status" in d["result_snapshot"], \
            f"result_snapshot missing solver_status: {d['result_snapshot']!r}"
        # The capacity scenario is a pre-solver data gap, so the *exact*
        # documented contract value must be 'data_gaps' (the OR-Tools model
        # is never built for this cycle). See test_infeasible_solver_capacity_vs_meeting
        # for the separate real-OR-Tools-infeasible path.
        solver_status = d["result_snapshot"]["solver_status"]
        assert solver_status == "data_gaps", \
            f"capacity-gap run must carry solver_status 'data_gaps', got {solver_status!r}"
        # The infeasible_causes must explicitly carry the capacity gap code.
        assert "ENROLLMENT_EXCEEDS_ROOM_CAPACITY" in codes, \
            f"expected ENROLLMENT_EXCEEDS_ROOM_CAPACITY cause, got {codes!r}"


    def test_infeasible_solver_conflict(self, client, db_session):
        """Real OR-Tools-driven infeasible run (distinct from data_gaps).

        Two offerings share one instructor AND one room; both demand a
        90-minute Saturday meeting, but the instructor is only free
        08:00-08:30 and the room only 08:00-08:15. All data is complete
        (nominations present, capacities OK, availability present) so
        ``_data_gaps`` emits nothing. The OR-Tools model is then built;
        its hard constraints make it INFEASIBLE. The run terminates
        infeasible with ``result_snapshot.solver_status == 'INFEASIBLE'``
        (a CpSolverStatus, NOT a 'data_gaps' marker). This is the
        counterpart of ``test_infeasible_capacity_gap`` and must remain
        an independent test with its own exact expectation.
        """
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering_a = _mk_offering(client, token, cycle, course,
                                  required_room_capacity=40,
                                  duration_minutes=90)
        course_b = _mk_course(client, token, code="CS102")
        offering_b = _mk_offering(client, token, cycle, course_b,
                                  required_room_capacity=40,
                                  duration_minutes=90)
        room = _mk_resource(client, token, "room", "Shared-Room", 40)
        inst = _mk_resource(client, token, "instructor", "Shared-Inst")
        # Instructor free 08:00-08:30; room free 08:00-08:15 — both Sat.
        _mk_availability(client, token, inst, cycle, weekday=2,
                         start="08:00", end="08:30")
        _mk_availability(client, token, room, cycle, weekday=2,
                         start="08:00", end="08:15")
        _mk_meeting_req(client, token, offering_a,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="09:00")
        _mk_meeting_req(client, token, offering_b,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="09:00")
        _link_unit_to_offering(client, token, offering_a, unit, enrollment=20)
        _link_unit_to_offering(client, token, offering_b, unit, enrollment=20)
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
        # Nominate the SAME room+instructor for both offerings.
        _nominate_offering(client, token, offering_a, unit, room, inst)
        _nominate_offering(client, token, offering_b, unit, room, inst)

        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "infeasible", body
        assert body["objective_score"] is None
        assert body["can_publish"] is False
        assert len(body["infeasible_causes"]) > 0
        run_id = body["run_id"]
        d = client.get(f"/phase4/runs/{run_id}",
                        headers=_auth_headers(token)).json()
        # No partial assignments on an infeasible run.
        assert len(d["assignments"]) == 0
        # Real OR-Tools path: CpSolverStatus name, NOT 'data_gaps'.
        solver_status = d["result_snapshot"]["solver_status"]
        assert solver_status == "INFEASIBLE", \
            f"expected OR-Tools 'INFEASIBLE', got {solver_status!r}"
        # Causes must NOT carry any data-gap marker.
        codes = [b["code"] for b in body["infeasible_causes"]]
        assert "ENROLLMENT_EXCEEDS_ROOM_CAPACITY" not in codes
        assert "NO_RESOURCE_AVAILABILITY" not in codes
        assert "Q12_RESOURCES_NOT_NOMINATED" not in codes
        # Persisted run snapshot also carries the CpSolverStatus.
        from app.models.phase4 import SolverRun
        db = SessionLocal()
        run = db.get(SolverRun, run_id)
        db.close()
        assert run.status == "infeasible"
        assert run.result_snapshot["solver_status"] == "INFEASIBLE"


    def test_infeasible_no_nomination(self, client, db_session):
        """Missing Q12 nomination is a hard preflight blocker, not a solver run.

        Without a nominated room/instructor the solve is blocked at the
        preflight gate (07: a blocker prevents the solver from running) and
        the endpoint returns 409 PREFLIGHT_BLOCKED carrying
        Q12_RESOURCES_NOT_NOMINATED — no SolverRun row is created.

        This mirrors test_q12_not_nominated in TestPreflightBlockers; it is
        kept here to document that a 'no nomination' cycle must never reach
        the solver (i.e. it is not reported as a 200 infeasible run).
        """
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering = _mk_offering(client, token, cycle, course,
                               required_room_capacity=20)
        room = _mk_resource(client, token, "room", "Room-1", 40)
        inst = _mk_resource(client, token, "instructor", "Inst-1")
        _mk_availability(client, token, room, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_availability(client, token, inst, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_meeting_req(client, token, offering,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="13:00")
        link = _link_unit_to_offering(client, token, offering, unit,
                                      enrollment=20)
        # NOTE: _nominate_offering NOT called → Q12 not nominated
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
        # Do NOT call _nominate_offering
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "PREFLIGHT_BLOCKED"
        codes = [b["code"] for b in detail["blockers"]]
        # Should contain Q12_RESOURCES_NOT_NOMINATED
        assert "Q12_RESOURCES_NOT_NOMINATED" in codes
        # No SolverRun was created for a blocked solve.
        from app.models.phase4 import SolverRun
        runs = db_session.query(SolverRun).filter(
            SolverRun.cycle_id == cycle["id"]).all()
        assert len(runs) == 0


class TestCorrectionWorkflow:
    """09 Manager correction track: append-only OfferingCorrection rows,

    stale-marking of approvals + solver runs, and corrections API.

    The correction workflow lets an admin modify a mutable offering field
    without rewriting the unit's original submission data. After a
    correction touching approval-affecting data, existing approvals are
    marked stale and non-stale solver runs of the cycle are marked stale.
    """

    def test_record_correction_and_stale_approvals(self, client, db_session):
        """Record a correction and verify a real approval + runs go stale.

        A real SharedOfferingApproval is first created through the legit API
        path (POST /phase3/offerings/{id}/shared-approvals) and the count is
        asserted *before* the correction — the test must not pass on an empty
        approval list. After posting /phase4/corrections with an
        approval-affecting field (expected_enrollment), the pre-existing
        approval should have stale=True and stale_reason set, and any
        non-stale solver runs of the cycle should also be stale-marked.
        """
        from app.database import SessionLocal
        from app.models.phase4 import OfferingCorrection, SolverRun
        from app.models.phase3 import SharedOfferingApproval
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering = _mk_offering(client, token, cycle, course,
                               required_room_capacity=20)
        room = _mk_resource(client, token, "room", "Room-1", 40)
        inst = _mk_resource(client, token, "instructor", "Inst-1")
        _mk_availability(client, token, room, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_availability(client, token, inst, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_meeting_req(client, token, offering,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="13:00")
        link = _link_unit_to_offering(client, token, offering, unit,
                                      enrollment=20)
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
        _nominate_offering(client, token, offering, unit, room, inst)
        # Create ONE real approval through the legit shared-approvals path.
        _record_shared_approval(client, token, offering, unit,
                                status="unit_approved")

        # Preflight state: exactly one real approval, not yet stale.
        db = SessionLocal()
        pre_approvals = db.query(SharedOfferingApproval).filter(
            SharedOfferingApproval.offering_id == offering["id"]).all()
        db.close()
        assert len(pre_approvals) == 1, \
            f"expected 1 approval, got {len(pre_approvals)}"
        assert pre_approvals[0].stale is False
        assert pre_approvals[0].stale_reason is None

        # Run solver first — must be feasible.
        r = client.post("/phase4/solve",
                        json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]
        assert r.json()["status"] == "feasible"

        # Record a correction touching an approval-affecting field.
        r = client.post(
            "/phase4/corrections",
            json={
                "cycle_id": cycle["id"],
                "offering_id": offering["id"],
                "field": "expected_enrollment",
                "before_value": "20",
                "after_value": "25",
                "reason": "Updated enrollment numbers"
            },
            headers=_auth_headers(token))
        assert r.status_code == 200, r.text
        correction_id = r.json()["id"]

        # The pre-existing approval is now stale with a non-empty reason.
        db = SessionLocal()
        approvals = db.query(SharedOfferingApproval).filter(
            SharedOfferingApproval.offering_id == offering["id"]).all()
        db.close()
        assert len(approvals) == 1, \
            f"approval count changed unexpectedly: {len(approvals)}"
        for a in approvals:
            assert a.stale is True, f"Approval {a.id} should be stale"
            assert a.stale_reason is not None, \
                "stale approval must carry a reason"
            assert f"offering_correction#{correction_id}" in a.stale_reason, \
                f"reason should reference the correction, got {a.stale_reason!r}"

        # The earlier feasible run is now stale-marked too.
        db = SessionLocal()
        run = db.get(SolverRun, run_id)
        db.close()
        assert run is not None, "feasible run vanished"
        assert run.stale is True, "run should be stale after correction"
        assert run.stale_reason is not None
        assert f"offering_correction#{correction_id}" in run.stale_reason

        # Second correction on the same offering still succeeds (append-only).
        r2 = client.post(
            "/phase4/corrections",
            json={
                "cycle_id": cycle["id"],
                "offering_id": offering["id"],
                "field": "expected_enrollment",
                "before_value": "20",
                "after_value": "30",
                "reason": "Second correction"
            },
            headers=_auth_headers(token))
        assert r2.status_code == 200, r2.text

    def test_correction_keeps_runs_stale_on_repeated_corrections(self, client, db_session):
        """Repeated corrections keep the stale flag persistently set.

        Contract (09): stale-marking is *write-only* — a correction marks
        the offering's non-stale runs stale, and a later correction on the
        same cycle does NOT clear the flag on those runs (they remain stale
        until a fresh solve produces a new run). This test asserts that
        behaviour: run1 (feasible) → correction #1 → run1.stale=True →
        correction #2 → run1.stale still True.
        """
        from app.models.phase4 import SolverRun
        token = _login_admin(client)["access_token"]
        cycle = _mk_cycle(client, token, status="submitted")
        unit = _mk_unit(client, token)
        course = _mk_course(client, token)
        offering = _mk_offering(client, token, cycle, course,
                               required_room_capacity=20)
        room = _mk_resource(client, token, "room", "Room-1", 40)
        inst = _mk_resource(client, token, "instructor", "Inst-1")
        _mk_availability(client, token, room, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_availability(client, token, inst, cycle, weekday=2,
                         start="08:00", end="14:00")
        _mk_meeting_req(client, token, offering,
                        allowed_weekday_min=2, allowed_weekday_max=2,
                        start_window_hhmm="08:00", end_window_hhmm="13:00")
        link = _link_unit_to_offering(client, token, offering, unit,
                                      enrollment=20)
        client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                    json={"unit_id": unit["id"]},
                    headers=_auth_headers(token))
        sub = _mk_submission(client, token, cycle, unit)
        sub = _submit(client, token, sub)
        _approve(client, token, sub)
        _nominate_offering(client, token, offering, unit, room, inst)
        r = client.post("/phase4/solve", json={"cycle_id": cycle["id"]},
                        headers=_auth_headers(token))
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        # Verify run is feasible before correction
        assert r.json()["status"] == "feasible"
        # Record a correction
        client.post(
            "/phase4/corrections",
            json={
                "cycle_id": cycle["id"],
                "offering_id": offering["id"],
                "field": "expected_enrollment",
                "before_value": "20",
                "after_value": "25",
                "reason": "Enrollment updated"
            },
            headers=_auth_headers(token))
        # Check run is now stale via API. get_run returns {"run": {...},
        # "input_snapshot", "result_snapshot", "assignments"}; the stale flag
        # lives on the nested "run" object (SolverRunRead.stale).
        r2 = client.get(f"/phase4/runs/{run_id}",
                        headers=_auth_headers(token))
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["run"]["stale"] is True
        # Second correction should keep runs stale (not recover)
        client.post(
            "/phase4/corrections",
            json={
                "cycle_id": cycle["id"],
                "offering_id": offering["id"],
                "field": "expected_enrollment",
                "before_value": "25",
                "after_value": "30",
                "reason": "Another correction"
            },
            headers=_auth_headers(token))
        r3 = client.get(f"/phase4/runs/{run_id}", headers=_auth_headers(token))
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["run"]["stale"] is True
