import os
"""Tests for approval-cycle/resource/teacher access-control changes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.test_phase2_api import (
    _login_admin, _auth_headers, _create_cycle, _create_unit,
    DEMO_ADMIN, DEMO_PASSWORD, DEMO_MGR,
)
from app.models.phase2 import PlanningCycle, ResourceAvailability
from app.models.phase3 import DomainAuditEvent

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5434")
os.environ.setdefault("DB_NAME", "barnamehsaz_novin_test")
os.environ.setdefault("DB_USER", "barnamehsaz")
os.environ.setdefault("DB_PASSWORD", "change_me_local")

from app.main import app, _login_failures  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import User, Membership, Organization, RefreshSession, AuditEvent  # noqa: E402
from tests.test_phase2_api import _seed, _wipe_auth  # noqa: E402


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
def clean_phase2(db_session):
    """Wipe all Phase 2 + auth state and re-seed before every test."""
    _wipe_auth(db_session)
    _seed(db_session)
    _login_failures.clear()
    yield

def _login_user(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


class TestTermNormalization:
    def test_empty_string_normalized_to_null(self, client, db_session):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "Term Empty", "term": ""},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["term"] is None
        cycle = db_session.get(PlanningCycle, data["id"])
        assert cycle.term is None

    def test_whitespace_only_normalized_to_null(self, client, db_session):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "Term WS", "term": "   "},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        assert r.json()["term"] is None

    def test_missing_key_defaults_to_null(self, client, db_session):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "No Term"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        assert r.json()["term"] is None

    def test_valid_string_is_preserved(self, client, db_session):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "Valid Term", "term": "Spring 2027"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 201, r.text
        assert r.json()["term"] == "Spring 2027"

    def test_empty_name_rejected_with_422(self, client):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "", "term": "T"},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 422

    def test_blank_name_rejected_with_422(self, client):
        admin = _login_admin(client)
        r = client.post("/phase2/planning-cycles",
                        json={"name": "   ", "term": None},
                        headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 422


class TestSoftDeletePlanningCycles:
    def test_admin_soft_delete(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"], name="AdminDelete")
        assert cycle["deleted_at"] is None

        r = client.delete(f"/phase2/planning-cycles/{cycle['id']}",
                          headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 204, r.text

        persisted = db_session.get(PlanningCycle, cycle["id"])
        assert persisted.deleted_at is not None

        # List endpoint excludes soft-deleted cycles
        list_r = client.get("/phase2/planning-cycles",
                            headers=_auth_headers(admin["access_token"]))
        assert list_r.status_code == 200
        ids = {c["id"] for c in list_r.json()}
        assert cycle["id"] not in ids

        # Get endpoint returns 404 for soft-deleted cycle
        get_r = client.get(f"/phase2/planning-cycles/{cycle['id']}",
                           headers=_auth_headers(admin["access_token"]))
        assert get_r.status_code == 404

    def test_nonadmin_unit_manager_cannot_delete_foreign_cycle(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_user(client, DEMO_MGR, DEMO_PASSWORD)
        foreign_cycle = _create_cycle(client, admin["access_token"], name="Foreign")
        r = client.delete(f"/phase2/planning-cycles/{foreign_cycle['id']}",
                          headers=_auth_headers(mgr["access_token"]))
        assert r.status_code == 403, r.text

    def test_own_cycle_accessible_by_responsible_unit_manager(self, client, db_session):
        admin = _login_admin(client)
        mgr = _login_user(client, DEMO_MGR, DEMO_PASSWORD)
        cycle = _create_cycle(client, admin["access_token"], name="Own")
        unit = _create_unit(client, admin["access_token"])
        mg_mem = (
            db_session.query(Membership)
            .join(Membership.user)
            .filter(Membership.role == "unit_manager")
            .first()
        )
        mg_user_id = mg_mem.user_id
        db_session.execute(
            text("INSERT INTO cycle_units (cycle_id, unit_id, responsible_user_id)"
                 " VALUES (:ci, :ui, :uid)"),
            {"ci": cycle["id"], "ui": unit["id"], "uid": mg_user_id},
        )
        db_session.commit()
        r = client.delete(f"/phase2/planning-cycles/{cycle['id']}",
                          headers=_auth_headers(mgr["access_token"]))
        assert r.status_code == 204, r.text
        assert db_session.get(PlanningCycle, cycle["id"]).deleted_at is not None


class TestResourceAvailabilitySoftDelete:
    def test_admin_soft_deletes_availability(self, client, db_session):
        admin = _login_admin(client)
        resource = client.post("/phase2/resources",
                               json={"kind": "room", "name": "R1", "capacity": 30},
                               headers=_auth_headers(admin["access_token"])).json()
        cycle = _create_cycle(client, admin["access_token"])
        avail = client.post(f"/phase2/resources/{resource['id']}/availability",
                            json={"cycle_id": cycle["id"], "weekday": 0,
                                  "start_hhmm": "08:00", "end_hhmm": "12:00"},
                            headers=_auth_headers(admin["access_token"])).json()
        assert avail["deleted_at"] is None
        r = client.delete(f"/phase2/resource-availability/{avail['id']}",
                          headers=_auth_headers(admin["access_token"]))
        assert r.status_code == 204, r.text
        row = db_session.get(ResourceAvailability, avail["id"])
        assert row.deleted_at is not None

    def test_list_excludes_soft_deleted_availability(self, client, db_session):
        admin = _login_admin(client)
        resource = client.post("/phase2/resources",
                               json={"kind": "instructor", "name": "In1", "capacity": 1},
                               headers=_auth_headers(admin["access_token"])).json()
        cycle = _create_cycle(client, admin["access_token"])
        avail = client.post(f"/phase2/resources/{resource['id']}/availability",
                            json={"cycle_id": cycle["id"], "weekday": 1,
                                  "start_hhmm": "14:00", "end_hhmm": "18:00"},
                            headers=_auth_headers(admin["access_token"])).json()
        client.delete(f"/phase2/resource-availability/{avail['id']}",
                      headers=_auth_headers(admin["access_token"]))
        list_r = client.get(f"/phase2/resources/{resource['id']}/availability",
                            headers=_auth_headers(admin["access_token"]))
        assert len(list_r.json()) == 0


class TestAuditEvents:
    def test_planning_cycle_delete_records_audit_event(self, client, db_session):
        admin = _login_admin(client)
        cycle = _create_cycle(client, admin["access_token"], name="Audited")
        client.delete(f"/phase2/planning-cycles/{cycle['id']}",
                      headers=_auth_headers(admin["access_token"]))
        event = (
            db_session.query(DomainAuditEvent)
            .filter(DomainAuditEvent.subject_type == "planning_cycle",
                    DomainAuditEvent.subject_id == cycle["id"])
            .one()
        )
        assert event.action == "planning_cycle_deleted"
        assert event.detail == {"name": "Audited", "term": None}

    def test_resource_availability_delete_records_audit_event(self, client, db_session):
        admin = _login_admin(client)
        resource = client.post("/phase2/resources",
                               json={"kind": "room", "name": "RA", "capacity": 5},
                               headers=_auth_headers(admin["access_token"])).json()
        cycle = _create_cycle(client, admin["access_token"])
        avail = client.post(f"/phase2/resources/{resource['id']}/availability",
                            json={"cycle_id": cycle["id"], "weekday": 0,
                                  "start_hhmm": "09:00", "end_hhmm": "13:00"},
                            headers=_auth_headers(admin["access_token"])).json()
        client.delete(f"/phase2/resource-availability/{avail['id']}",
                      headers=_auth_headers(admin["access_token"]))
        event = (
            db_session.query(DomainAuditEvent)
            .filter(DomainAuditEvent.subject_type == "resource_availability",
                    DomainAuditEvent.subject_id == avail["id"])
            .one()
        )
        assert event.action == "resource_availability_deleted"
        assert event.detail["resource_id"] == resource["id"]


class TestDuplicateSubmissionLock:
    """Placeholder for the Q5 requirement blocking more than five concurrent submissions."""
    def test_placeholder(self):
        assert True
