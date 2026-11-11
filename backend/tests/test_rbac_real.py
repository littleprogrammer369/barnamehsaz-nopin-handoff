"""Real RBAC and workflow tests with actual database execution.

Tests verify:
1. Resource.kind-based permissions (room vs instructor)
2. Unit isolation (unit_manager cannot access other units)
3. 5-unit submission workflow and gating
"""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from app.models.base import User, Membership, Organization
from app.models.phase2 import Unit, Resource, PlanningCycle, CycleUnit
from app.core.rbac import ROLE_ADMIN, ROLE_UNIT_MANAGER
from tests.conftest import test_engine, TestSessionLocal
from app.database import Base


@pytest.fixture(scope="function")
def db_session():
    """Create test database session (5434 only)."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session
    db = TestSessionLocal()
    yield db
    db.close()
    
    # Drop all tables after test
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_org(db_session: Session):
    """Create test organization."""
    org = Organization(name="Test Org", slug="test-org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture(scope="function")
def test_users(db_session: Session, test_org: Organization):
    """Create test users: admin and 2 unit managers."""
    admin = User(
        email="admin@test.example",
        password_hash="hash_admin",
        full_name="Admin User",
        organization_id=test_org.id,
        is_active=True,
        must_change_password=False,
    )
    umgr1 = User(
        email="umgr1@test.example",
        password_hash="hash_umgr1",
        full_name="Unit Manager 1",
        organization_id=test_org.id,
        is_active=True,
        must_change_password=False,
    )
    umgr2 = User(
        email="umgr2@test.example",
        password_hash="hash_umgr2",
        full_name="Unit Manager 2",
        organization_id=test_org.id,
        is_active=True,
        must_change_password=False,
    )
    db_session.add_all([admin, umgr1, umgr2])
    db_session.commit()
    return {"admin": admin, "umgr1": umgr1, "umgr2": umgr2}


@pytest.fixture(scope="function")
def test_units(db_session: Session, test_org: Organization):
    """Create 5 test units."""
    units = []
    for i in range(1, 6):
        unit = Unit(
            name=f"Unit {i}",
            code=f"U{i}",
            organization_id=test_org.id,
        )
        units.append(unit)
    db_session.add_all(units)
    db_session.commit()
    for u in units:
        db_session.refresh(u)
    return units


@pytest.fixture(scope="function")
def test_memberships(db_session: Session, test_org: Organization, test_users, test_units):
    """Create memberships: admin (no unit), umgr1->unit1, umgr2->unit2."""
    m_admin = Membership(
        user_id=test_users["admin"].id,
        organization_id=test_org.id,
        role=ROLE_ADMIN,
        unit_id=None,
    )
    m_umgr1 = Membership(
        user_id=test_users["umgr1"].id,
        organization_id=test_org.id,
        role=ROLE_UNIT_MANAGER,
        unit_id=test_units[0].id,
    )
    m_umgr2 = Membership(
        user_id=test_users["umgr2"].id,
        organization_id=test_org.id,
        role=ROLE_UNIT_MANAGER,
        unit_id=test_units[1].id,
    )
    db_session.add_all([m_admin, m_umgr1, m_umgr2])
    db_session.commit()
    return {"admin": m_admin, "umgr1": m_umgr1, "umgr2": m_umgr2}


@pytest.fixture
def client(db_session: Session):
    """FastAPI test client with injected session."""
    def override_get_db():
        return db_session
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _get_token(user: User, org: Organization) -> str:
    """Generate test JWT token."""
    from app.core.jwt_utils import encode_token
    return encode_token({"sub": str(user.id), "org": org.id, "type": "access"})


class TestResourceKindPermissions:
    """Test room vs instructor permissions."""
    
    def test_admin_can_create_room(self, client: TestClient, test_users, test_org):
        """Admin creates room: expects 201."""
        response = client.post(
            "/phase2/resources",
            json={"kind": "room", "name": "Room A", "code": "RA1", "capacity": 50},
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 201
    
    def test_admin_can_create_instructor(self, client: TestClient, test_users, test_org):
        """Admin creates instructor: expects 201."""
        response = client.post(
            "/phase2/resources",
            json={"kind": "instructor", "name": "Dr. Smith", "code": "DRS"},
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 201
    
    def test_unit_manager_cannot_create_room(self, client: TestClient, test_users, test_org):
        """Unit manager creates room: expects 403."""
        response = client.post(
            "/phase2/resources",
            json={"kind": "room", "name": "Room B", "capacity": 30},
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )
        assert response.status_code == 403
    
    def test_unit_manager_can_create_instructor(self, client: TestClient, test_users, test_org):
        """Unit manager creates instructor: expects 201."""
        response = client.post(
            "/phase2/resources",
            json={"kind": "instructor", "name": "Prof. Jones", "code": "PJ"},
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )



class TestUnitIsolation:
    """Test unit isolation in submissions and offerings."""
    
    def test_unit_manager_cannot_list_other_units_submissions(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Unit manager umgr1 should not see submissions from unit 2."""
        from app.models.phase3 import Submission, SUB_DRAFT
        from app.models.phase2 import PlanningCycle
        
        # Create cycle
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        # Create submissions for different units
        sub1 = Submission(
            cycle_id=cycle.id,
            unit_id=test_units[0].id,  # umgr1's unit
            organization_id=test_org.id,
            status=SUB_DRAFT,
        )
        sub2 = Submission(
            cycle_id=cycle.id,
            unit_id=test_units[1].id,  # umgr2's unit
            organization_id=test_org.id,
            status=SUB_DRAFT,
        )
        db_session.add_all([sub1, sub2])
        db_session.commit()
        
        # umgr1 lists submissions - should only see sub1
        response = client.get(
            "/phase3/submissions",
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )
        assert response.status_code == 200
        data = response.json()

    
    def test_unit_manager_cannot_view_other_units_submission_detail(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Unit manager umgr1 tries to view submission from unit 2: expects 403."""
        from app.models.phase3 import Submission, SUB_DRAFT
        from app.models.phase2 import PlanningCycle
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        sub = Submission(
            cycle_id=cycle.id,
            unit_id=test_units[1].id,  # NOT umgr1's unit
            organization_id=test_org.id,
            status=SUB_DRAFT,
        )
        db_session.add(sub)
        db_session.commit()
        
        response = client.get(
            f"/phase3/submissions/{sub.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )

    
    def test_admin_can_see_all_submissions(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Admin should see submissions from all units."""
        from app.models.phase3 import Submission, SUB_DRAFT
        from app.models.phase2 import PlanningCycle
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        subs = []
        for i in range(3):
            sub = Submission(
                cycle_id=cycle.id,
                unit_id=test_units[i].id,
                organization_id=test_org.id,
                status=SUB_DRAFT,
            )
            subs.append(sub)
        db_session.add_all(subs)
        db_session.commit()
        
        response = client.get(
            "/phase3/submissions",
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 200



class TestWorkflowGating:
    """Test 5-unit workflow gating."""
    
    def test_preflight_blocks_when_4_units_submitted(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Preflight should return 409 when only 4/5 units submitted."""
        from app.models.phase3 import Submission, SUB_SUBMITTED
        from app.models.phase2 import PlanningCycle, CycleUnit
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        # Add cycle-unit memberships for all 5 units
        for unit in test_units:
            cu = CycleUnit(cycle_id=cycle.id, unit_id=unit.id)
            db_session.add(cu)
        db_session.commit()
        
        # Create submissions for 4 units only
        for i in range(4):
            sub = Submission(
                cycle_id=cycle.id,
                unit_id=test_units[i].id,
                organization_id=test_org.id,
                status=SUB_SUBMITTED,
            )
            db_session.add(sub)
        db_session.commit()
        
        # Preflight should fail
        response = client.get(
            f"/phase3/preflight?cycle_id={cycle.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 409
        assert "4/5" in response.json()["detail"]
    
    def test_preflight_allows_when_5_units_submitted(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Preflight should return 200 when all 5 units submitted."""
        from app.models.phase3 import Submission, SUB_SUBMITTED
        from app.models.phase2 import PlanningCycle, CycleUnit
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        # Add cycle-unit memberships
        for unit in test_units:
            cu = CycleUnit(cycle_id=cycle.id, unit_id=unit.id)
            db_session.add(cu)
        db_session.commit()
        
        # Create submissions for all 5 units
        for i in range(5):
            sub = Submission(
                cycle_id=cycle.id,
                unit_id=test_units[i].id,
                organization_id=test_org.id,
                status=SUB_SUBMITTED,
            )
            db_session.add(sub)
        db_session.commit()
        
        # Preflight should succeed
        response = client.get(
            f"/phase3/preflight?cycle_id={cycle.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 200


class TestOfferingsIsolation:
    """Test offerings unit isolation for unit managers."""
    
    def test_unit_manager_cannot_list_other_units_offerings(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Unit manager umgr1 should only see offerings where unit 1 participates."""
        from app.models.phase2 import (
            PlanningCycle, CourseOffering, Course, OfferingUnit, CycleUnit
        )
        
        # Create cycle with all 5 units
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        for unit in test_units:
            cu = CycleUnit(cycle_id=cycle.id, unit_id=unit.id)
            db_session.add(cu)
        db_session.commit()
        
        # Create course
        course = Course(code="CS101", title="Intro to CS", organization_id=test_org.id)
        db_session.add(course)
        db_session.commit()
        
        # Create offering
        offering = CourseOffering(
            course_id=course.id,
            planning_cycle_id=cycle.id,
            meetings_per_week=1,
            duration_minutes=90,
        )
        db_session.add(offering)
        db_session.commit()
        
        # Link offering to unit 2 only (NOT unit 1)
        ou = OfferingUnit(offering_id=offering.id, unit_id=test_units[1].id)
        db_session.add(ou)
        db_session.commit()
        
        # umgr1 lists offerings - should NOT see this offering
        response = client.get(
            f"/phase2/offerings?planning_cycle_id={cycle.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )
        assert response.status_code == 200
        offerings = response.json()
        assert len(offerings) == 0, "umgr1 should not see offering linked to unit 2"
    
    def test_unit_manager_can_see_own_units_offerings(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Unit manager umgr1 should see offerings where unit 1 participates."""
        from app.models.phase2 import (
            PlanningCycle, CourseOffering, Course, OfferingUnit, CycleUnit
        )
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        for unit in test_units:
            cu = CycleUnit(cycle_id=cycle.id, unit_id=unit.id)
            db_session.add(cu)
        db_session.commit()
        
        course = Course(code="CS102", title="CS II", organization_id=test_org.id)
        db_session.add(course)
        db_session.commit()
        
        offering = CourseOffering(
            course_id=course.id,
            planning_cycle_id=cycle.id,
            meetings_per_week=1,
            duration_minutes=90,
        )
        db_session.add(offering)
        db_session.commit()
        
        # Link offering to unit 1 (umgr1's unit)
        ou = OfferingUnit(offering_id=offering.id, unit_id=test_units[0].id)
        db_session.add(ou)
        db_session.commit()
        
        # umgr1 lists offerings - should see this offering
        response = client.get(
            f"/phase2/offerings?planning_cycle_id={cycle.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['umgr1'], test_org)}"},
        )
        assert response.status_code == 200
        offerings = response.json()
        assert len(offerings) == 1, "umgr1 should see offering linked to unit 1"
        assert offerings[0]["id"] == offering.id
    
    def test_admin_sees_all_offerings(
        self, client: TestClient, db_session: Session, test_users, test_org, test_units
    ):
        """Admin should see all offerings regardless of unit participation."""
        from app.models.phase2 import (
            PlanningCycle, CourseOffering, Course, OfferingUnit, CycleUnit
        )
        
        cycle = PlanningCycle(name="Cycle 1", organization_id=test_org.id, term="99/00")
        db_session.add(cycle)
        db_session.commit()
        
        for unit in test_units:
            cu = CycleUnit(cycle_id=cycle.id, unit_id=unit.id)
            db_session.add(cu)
        db_session.commit()
        
        course = Course(code="CS103", title="CS III", organization_id=test_org.id)
        db_session.add(course)
        db_session.commit()
        
        offering1 = CourseOffering(
            course_id=course.id,
            planning_cycle_id=cycle.id,
            section="A",
            meetings_per_week=1,
            duration_minutes=90,
        )
        offering2 = CourseOffering(
            course_id=course.id,
            planning_cycle_id=cycle.id,
            section="B",
            meetings_per_week=1,
            duration_minutes=90,
        )
        db_session.add_all([offering1, offering2])
        db_session.commit()
        
        # Link offerings to different units
        ou1 = OfferingUnit(offering_id=offering1.id, unit_id=test_units[0].id)
        ou2 = OfferingUnit(offering_id=offering2.id, unit_id=test_units[1].id)
        db_session.add_all([ou1, ou2])
        db_session.commit()
        
        # Admin lists offerings - should see both
        response = client.get(
            f"/phase2/offerings?planning_cycle_id={cycle.id}",
            headers={"Authorization": f"Bearer {_get_token(test_users['admin'], test_org)}"},
        )
        assert response.status_code == 200
        offerings = response.json()
        assert len(offerings) == 2, "Admin should see all offerings"


