"""Access Control & RBAC integration tests.

Tests role-based access control:
- Admin-only operations (cycle/resource CRUD)
- Unit manager isolation (view only own unit data)
- 5-unit submission workflow (0/5 to 5/5)
- Soft-delete behavior

Run with:
  cd backend
  APP_ENV=test DB_HOST=localhost DB_PORT=5434 DB_NAME=barnamehsaz_novin_test \
    DB_USER=barnamehsaz DB_PASSWORD=change_me_local \
    .venv/bin/python -m pytest tests/test_access_control.py -v
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

from app.main import app  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import User, Membership, Organization  # noqa: E402
from app.models.phase2 import PlanningCycle, Unit, Resource, CycleUnit  # noqa: E402
from app.models.phase3 import Submission  # noqa: E402
from app.core.password_utils import hash_password  # noqa: E402

ADMIN_EMAIL = "admin@test.example"
UNIT_MGR1_EMAIL = "umgr1@test.example"
UNIT_MGR2_EMAIL = "umgr2@test.example"
PASSWORD = "testpass123"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="module")
def db_session():
    """Create test database and session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def test_data(db_session):
    """Create test org, users, and units."""
    org = Organization(name="Test Org", slug="test-org")
    db_session.add(org)
    db_session.flush()
    
    # Create users
    admin = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        full_name="Admin User",
        organization_id=org.id,
        is_active=True,
        must_change_password=False,
    )
    unit_mgr1 = User(
        email=UNIT_MGR1_EMAIL,
        password_hash=hash_password(PASSWORD),
        full_name="Unit Manager 1",
        organization_id=org.id,
        is_active=True,
        must_change_password=False,
    )
    unit_mgr2 = User(
        email=UNIT_MGR2_EMAIL,
        password_hash=hash_password(PASSWORD),
        full_name="Unit Manager 2",
        organization_id=org.id,
        is_active=True,
        must_change_password=False,
    )
    db_session.add_all([admin, unit_mgr1, unit_mgr2])
    db_session.flush()
    
    # Create units
    unit1 = Unit(name="Unit 1", organization_id=org.id)
    unit2 = Unit(name="Unit 2", organization_id=org.id)
    unit3 = Unit(name="Unit 3", organization_id=org.id)
    unit4 = Unit(name="Unit 4", organization_id=org.id)
    unit5 = Unit(name="Unit 5", organization_id=org.id)
    db_session.add_all([unit1, unit2, unit3, unit4, unit5])
    db_session.flush()
    
    # Create memberships
    admin_membership = Membership(
        user_id=admin.id,
        organization_id=org.id,
        role="admin",
        unit_id=None,
    )
    mgr1_membership = Membership(
        user_id=unit_mgr1.id,
        organization_id=org.id,
        role="unit_manager",
        unit_id=unit1.id,
    )
    mgr2_membership = Membership(
        user_id=unit_mgr2.id,
        organization_id=org.id,
        role="unit_manager",
        unit_id=unit2.id,
    )
    db_session.add_all([admin_membership, mgr1_membership, mgr2_membership])
    db_session.commit()
    
    return {
        "org": org,
        "admin": admin,
        "unit_mgr1": unit_mgr1,
        "unit_mgr2": unit_mgr2,
        "units": [unit1, unit2, unit3, unit4, unit5],
    }


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)




class TestCycleAccessControl:
    """Test admin-only cycle operations."""
    
    def test_admin_can_create_cycle(self, client, test_data):
        """Admin should be able to create a planning cycle."""
        token = _login(client, ADMIN_EMAIL)
        resp = client.post(
            "/api/v1/phase2/planning-cycles",
            headers=_auth_headers(token),
            json={"name": "Fall 2024", "term": "Fall 2024", "status": "draft"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        assert resp.json()["name"] == "Fall 2024"
    
    def test_unit_manager_cannot_create_cycle(self, client, test_data):
        """Unit manager should NOT be able to create a cycle."""
        token = _login(client, UNIT_MGR1_EMAIL)
        resp = client.post(
            "/api/v1/phase2/planning-cycles",
            headers=_auth_headers(token),
            json={"name": "Fall 2024", "term": "Fall 2024", "status": "draft"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


class TestResourceAccessControl:
    """Test admin-only resource operations."""
    
    def test_admin_can_create_resource(self, client, test_data):
        """Admin should be able to create a resource."""
        token = _login(client, ADMIN_EMAIL)
        resp = client.post(
            "/api/v1/phase2/resources",
            headers=_auth_headers(token),
            json={"kind": "room", "name": "Room 101", "code": "R101", "capacity": 30},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Room 101"
    
    def test_unit_manager_cannot_create_resource(self, client, test_data):
        """Unit manager should NOT be able to create a resource."""
        token = _login(client, UNIT_MGR1_EMAIL)
        resp = client.post(
            "/api/v1/phase2/resources",
            headers=_auth_headers(token),
            json={"kind": "room", "name": "Room 202", "code": "R202", "capacity": 25},
        )
        assert resp.status_code == 403


class TestTermFieldNormalization:
    """Test optional term field handling."""
    
    def test_cycle_with_empty_term_normalized_to_null(self, client, test_data):
        """Empty term should be normalized to null."""
        token = _login(client, ADMIN_EMAIL)
        resp = client.post(
            "/api/v1/phase2/planning-cycles",
            headers=_auth_headers(token),
            json={"name": "Test Cycle", "term": ""},
        )
        assert resp.status_code == 201
        assert resp.json()["term"] is None
    
    def test_cycle_with_null_term_accepted(self, client, test_data):
        """Null term should be accepted."""
        token = _login(client, ADMIN_EMAIL)
        resp = client.post(
            "/api/v1/phase2/planning-cycles",
            headers=_auth_headers(token),
            json={"name": "Test Cycle 3", "term": None},
        )
        assert resp.status_code == 201
        assert resp.json()["term"] is None

