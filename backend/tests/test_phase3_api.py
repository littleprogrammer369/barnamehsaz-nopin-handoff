"""Phase 3 integration tests: submissions lifecycle, revisions, wizard state,
shared-offering approvals, preflight, and cross-org isolation.

Run with:
  cd backend
  APP_ENV=test DB_HOST=localhost DB_PORT=5434 DB_NAME=barnamehsaz_novin_test \
    DB_USER=barnamehsaz DB_PASSWORD=change_me_local \
    .venv/bin/python -m pytest tests/test_phase3_api.py -v
"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5434")
os.environ.setdefault("DB_NAME", "barnamehsaz_novin_test")
os.environ.setdefault("DB_USER", "barnamehsaz")
os.environ.setdefault("DB_PASSWORD", "change_me_local")

from app.main import app, _login_failures  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import User, Membership, Organization, RefreshSession  # noqa: E402
from app.models.phase2 import (  # noqa: E402
    PlanningCycle, Unit, CycleUnit, Course, CourseOffering,
    OfferingUnit, Cohort, CycleCohort, MeetingRequirement,
)  # noqa: E402
from app.models.phase3 import (  # noqa: E402
    Submission, SubmissionRevision, SubmissionComment, WizardDraft,
    SharedOfferingApproval, DomainAuditEvent,
)  # noqa: E402
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
    # Wipe Phase 3 and Phase 2 state before each test
    db_session.query(DomainAuditEvent).delete()
    db_session.query(SharedOfferingApproval).delete()
    db_session.query(WizardDraft).delete()
    db_session.query(SubmissionComment).delete()
    db_session.query(SubmissionRevision).delete()
    db_session.query(Submission).delete()
    from app.models.phase2 import (
        MeetingRequirement, OfferingCohort, OfferingUnit, CourseOffering,
        Course, CycleCohort, Cohort, ResourceCommitment, ResourceAvailability,
        Resource, CycleUnit, PlanningCycle, Unit,
    )
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


def _login_mgr(client):
    r = client.post("/auth/login", json={"email": DEMO_MGR, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def _create_cycle(client, admin_token, name="Spring 2027", term="Spring 2027"):
    r = client.post("/phase2/planning-cycles", json={"name": name, "term": term},
                    headers=_auth_headers(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


def _create_unit(client, admin_token, name="CS Dept"):
    r = client.post("/phase2/units", json={"name": name},
                    headers=_auth_headers(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


def _create_course(client, admin_token, code="CS101", title="Intro to CS"):
    r = client.post("/phase2/courses", json={"code": code, "title": title},
                    headers=_auth_headers(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


def _create_offering(client, admin_token, cycle, course, section=None):
    body = {"course_id": course["id"], "planning_cycle_id": cycle["id"],
            "meetings_per_week": 1, "duration_minutes": 90}
    if section:
        body["section"] = section
    r = client.post("/phase2/offerings", json=body, headers=_auth_headers(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


def _link_offering_unit(client, admin_token, offering, unit, enrollment=0):
    r = client.post(f"/phase2/offerings/{offering['id']}/units",
                    json={"unit_id": unit["id"], "expected_enrollment": enrollment},
                    headers=_auth_headers(admin_token))
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------------------------------------------------------------------------
# Submissions lifecycle
# ---------------------------------------------------------------------------

class TestSubmissions:
    def test_create_draft(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post(f"/phase2/planning-cycles/{cycle['id']}/units",
                       json={"unit_id": unit["id"]},
                       headers=_auth_headers(admin["access_token"]))
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "draft"
        assert data["version"] == 0
        assert data["locked"] is False

    def test_create_submission_requires_auth(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]})
        assert r.status_code == 401

    def test_submit_draft(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        r = client.post(f"/phase3/submissions/{sub['id']}/submit",
                        json={"input_snapshot": {"units": [unit["id"]]}},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "submitted"
        assert data["locked"] is True
        assert data["version"] == 1

    def test_stale_version_returns_409(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        r = client.post(f"/phase3/submissions/{sub['id']}/submit",
                        json={"expected_version": 99},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 409

    def test_needs_changes_admin_only(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        client.post(f"/phase3/submissions/{sub['id']}/submit",
                    json={}, headers=_auth_headers(admin["access_token"]))
        r = client.post(f"/phase3/submissions/{sub['id']}/needs-changes",
                        json={"reason": "please fix"},
                        headers=_auth_headers(mgr["access_token"]))
        assert r.status_code == 403

    def test_needs_changes_then_resubmit(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        client.post(f"/phase3/submissions/{sub['id']}/submit", json={},
                    headers=_auth_headers(admin["access_token"]))
        r = client.post(f"/phase3/submissions/{sub['id']}/needs-changes",
                        json={"reason": "insufficient detail", "expected_version": 1},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "needs_changes"
        # resubmit
        r = client.post(f"/phase3/submissions/{sub['id']}/submit",
                        json={"input_snapshot": {"resubmitted": True}, "expected_version": 2},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "submitted"
        assert r.json()["version"] == 3

    def test_approve_admin_only(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        client.post(f"/phase3/submissions/{sub['id']}/submit", json={},
                    headers=_auth_headers(admin["access_token"]))
        r = client.post(f"/phase3/submissions/{sub['id']}/approve",
                        json={"expected_version": 1},
                        headers=_auth_headers(mgr["access_token"]))
        assert r.status_code == 403
        r = client.post(f"/phase3/submissions/{sub['id']}/approve",
                        json={"expected_version": 1},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_revisions_immutable(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        client.post(f"/phase3/submissions/{sub['id']}/submit",
                    json={"input_snapshot": {"v": 1}},
                    headers=_auth_headers(admin["access_token"]))
        r = client.get(f"/phase3/submissions/{sub['id']}/revisions",
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        revs = r.json()
        assert len(revs) == 1
        assert revs[0]["revision_no"] == 1
        assert revs[0]["input_snapshot"] == {"v": 1}
        # No DELETE endpoint exists
        r = client.delete(f"/phase3/submissions/{sub['id']}/revisions/1",
                          headers=_auth_headers(admin["access_token"]))
        assert r.status_code in (404, 405)

    def test_cross_org_isolation(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        sub_id = sub["id"]
        # Create a second org and its admin
        from app.models.base import Organization as Org
        from app.core.password_utils import hash_password as hp
        org2 = Org(name="Other Org", slug="other-org", timezone="Asia/Tehran")
        db_session.add(org2)
        db_session.flush()
        user2 = User(email="other@other.org", password_hash=hp(DEMO_PASSWORD),
                     full_name="Other Admin", must_change_password=False, is_active=True,
                     organization_id=org2.id)
        db_session.add(user2)
        db_session.flush()
        db_session.add(Membership(user_id=user2.id, organization_id=org2.id, role="admin"))
        db_session.commit()
        r = client.post("/auth/login", json={"email": "other@other.org", "password": DEMO_PASSWORD})
        assert r.status_code == 200
        other_token = r.json()["access_token"]
        r = client.get(f"/phase3/submissions/{sub_id}",
                       headers=_auth_headers(other_token))
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Wizard state
# ---------------------------------------------------------------------------

class TestWizardState:
    def test_save_and_resume(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/wizard-state",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"],
                              "section_state": {"step1": "done", "step2": "pending"}},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["section_state"]["step1"] == "done"
        r = client.get("/phase3/wizard-state",
                       params={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        assert r.json()["section_state"]["step2"] == "pending"

    def test_wizard_not_created_on_submission(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201
        r = client.get("/phase3/wizard-state",
                       params={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        assert r.json() is None


# ---------------------------------------------------------------------------
# Shared offering approvals
# ---------------------------------------------------------------------------

class TestSharedOfferings:
    def test_shared_approval_flow(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit1 = _create_unit(client, admin["access_token"], name="CS Dept")
        unit2 = _create_unit(client, admin["access_token"], name="EE Dept")
        course = _create_course(client, admin["access_token"])
        offering = _create_offering(client, admin["access_token"], cycle, course)
        _link_offering_unit(client, admin["access_token"], offering, unit1, 20)
        _link_offering_unit(client, admin["access_token"], offering, unit2, 15)
        off_id = offering["id"]
        # Admin records approval for unit1 (admin bypasses "own unit" gate)
        r = client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                        json={"status": "unit_approved", "unit_id": unit1["id"], "comment": "ok"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        # Admin records approval for unit2
        r = client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                        json={"status": "unit_approved", "unit_id": unit2["id"]},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        # Admin finalizes
        r = client.post(f"/phase3/offerings/{off_id}/shared-finalize",
                        json={"decision": "approve"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["outcome"] == "approved"

    def test_shared_finalize_blocked_without_all_approvals(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit1 = _create_unit(client, admin["access_token"], name="CS Dept")
        unit2 = _create_unit(client, admin["access_token"], name="EE Dept")
        course = _create_course(client, admin["access_token"])
        offering = _create_offering(client, admin["access_token"], cycle, course)
        _link_offering_unit(client, admin["access_token"], offering, unit1, 20)
        _link_offering_unit(client, admin["access_token"], offering, unit2, 15)
        off_id = offering["id"]
        # Admin records approval for unit1 (admin bypasses "own unit" gate)
        client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                    json={"status": "unit_approved", "unit_id": unit1["id"]},
                    headers=_auth_headers(admin["access_token"]))
        r = client.post(f"/phase3/offerings/{off_id}/shared-finalize",
                        json={"decision": "approve"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 409

    def test_return_re_pends_approvals(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit1 = _create_unit(client, admin["access_token"], name="CS Dept")
        course = _create_course(client, admin["access_token"])
        offering = _create_offering(client, admin["access_token"], cycle, course)
        _link_offering_unit(client, admin["access_token"], offering, unit1, 20)
        off_id = offering["id"]
        client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                    json={"status": "unit_approved", "unit_id": unit1["id"]},
                    headers=_auth_headers(mgr["access_token"]))
        r = client.post(f"/phase3/offerings/{off_id}/shared-finalize",
                        json={"decision": "return", "reason": "capacity too low"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        assert r.json()["re_pend_approvals"] is True
        # Approvals are now pending
        r = client.get(f"/phase3/offerings/{off_id}/shared-approvals",
                       headers=_auth_headers(admin["access_token"]))
        approvals = r.json()
        assert all(a["status"] == "pending" for a in approvals)

    def test_preflight_flags_unapproved_shared_offering(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit1 = _create_unit(client, admin["access_token"], name="CS Dept")
        unit2 = _create_unit(client, admin["access_token"], name="EE Dept")
        course = _create_course(client, admin["access_token"])
        offering = _create_offering(client, admin["access_token"], cycle, course)
        _link_offering_unit(client, admin["access_token"], offering, unit1, 20)
        _link_offering_unit(client, admin["access_token"], offering, unit2, 15)
        r = client.get("/phase3/preflight", params={"cycle_id": cycle["id"]},
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["can_submit"] is False
        codes = [b["code"] for b in data["blockers"]]
        assert "SHARED_OFFERING_UNAPPROVED" in codes

    def test_preflight_clean_after_approvals(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_mgr(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit1 = _create_unit(client, admin["access_token"], name="CS Dept")
        unit2 = _create_unit(client, admin["access_token"], name="EE Dept")
        course = _create_course(client, admin["access_token"])
        offering = _create_offering(client, admin["access_token"], cycle, course)
        _link_offering_unit(client, admin["access_token"], offering, unit1, 20)
        _link_offering_unit(client, admin["access_token"], offering, unit2, 15)
        off_id = offering["id"]
        # Admin records approval for both units (no submission needed for admin)
        r = client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                        json={"status": "unit_approved", "unit_id": unit1["id"]},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        r = client.post(f"/phase3/offerings/{off_id}/shared-approvals",
                        json={"status": "unit_approved", "unit_id": unit2["id"]},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        r = client.get("/phase3/preflight", params={"cycle_id": cycle["id"]},
                       headers=_auth_headers(admin["access_token"]))
        data = r.json()
        shared_blockers = [b for b in data["blockers"] if b["code"] == "SHARED_OFFERING_UNAPPROVED"]
        assert not shared_blockers


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_audit_events_written_on_submit(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub = r.json()
        client.post(f"/phase3/submissions/{sub['id']}/submit", json={},
                    headers=_auth_headers(admin["access_token"]))
        r = client.get("/phase3/audit-events",
                       params={"subject_type": "submission", "subject_id": sub["id"]},
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        events = r.json()
        actions = [e["action"] for e in events]
        assert "submit" in actions
        assert "submission_create" in actions

    def test_audit_events_org_scoped(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        client.post("/phase3/submissions",
                    json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                    headers=_auth_headers(admin["access_token"]))
        # Create org2 user
        from app.models.base import Organization as Org
        org2 = Org(name="Org2", slug="org2", timezone="Asia/Tehran")
        db_session.add(org2)
        db_session.flush()
        user2 = User(email="user2@other-org.example", password_hash=hash_password(DEMO_PASSWORD),
                     full_name="U2", must_change_password=False, is_active=True,
                     organization_id=org2.id)
        db_session.add(user2)
        db_session.flush()
        db_session.add(Membership(user_id=user2.id, organization_id=org2.id, role="admin"))
        db_session.commit()
        r = client.post("/auth/login", json={"email": "user2@other-org.example", "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.text
        other_token = r.json()["access_token"]
        r = client.get("/phase3/audit-events",
                       headers=_auth_headers(other_token))
        assert r.status_code == 200
        assert len(r.json()) == 0


# ---------------------------------------------------------------------------
# Comments / annotations
# ---------------------------------------------------------------------------

class TestComments:
    def test_add_comment_on_submission(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub_id = r.json()["id"]
        r = client.post(f"/phase3/submissions/{sub_id}/comments",
                        json={"text": "needs more detail on cohort enrollment"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["text"] == "needs more detail on cohort enrollment"
        assert data["revision_no"] is None

    def test_add_comment_on_revision(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub_id = r.json()["id"]
        # Submit to create a revision
        client.post(f"/phase3/submissions/{sub_id}/submit", json={},
                    headers=_auth_headers(admin["access_token"]))
        r = client.post(f"/phase3/submissions/{sub_id}/comments",
                        json={"text": "rev1 looks good", "target": "revision", "revision_no": 1},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        assert r.json()["revision_no"] == 1

    def test_list_comments(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub_id = r.json()["id"]
        client.post(f"/phase3/submissions/{sub_id}/comments",
                    json={"text": "first comment"},
                    headers=_auth_headers(admin["access_token"]))
        client.post(f"/phase3/submissions/{sub_id}/comments",
                    json={"text": "second comment"},
                    headers=_auth_headers(admin["access_token"]))
        r = client.get(f"/phase3/submissions/{sub_id}/comments",
                       headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 200
        comments = r.json()
        assert len(comments) == 2
        assert comments[0]["text"] == "first comment"
        assert comments[1]["text"] == "second comment"

    def test_comment_requires_auth(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub_id = r.json()["id"]
        r = client.post(f"/phase3/submissions/{sub_id}/comments",
                        json={"text": "unauthenticated"})
        assert r.status_code == 401

    def test_comment_revision_target_requires_revision_no(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"])
        unit = _create_unit(client, admin["access_token"])
        r = client.post("/phase3/submissions",
                        json={"cycle_id": cycle["id"], "unit_id": unit["id"]},
                        headers=_auth_headers(admin["access_token"]))
        sub_id = r.json()["id"]
        r = client.post(f"/phase3/submissions/{sub_id}/comments",
                        json={"text": "bad", "target": "revision"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 400
