"""Integration/API tests for authentication, refresh rotation, and RBAC (Phase 1 security closeout).

Run with:
  cd backend
  APP_ENV=test DB_HOST=localhost DB_PORT=5434 DB_NAME=barnamehsaz_novin_test \
    DB_USER=barnamehsaz DB_PASSWORD=change_me_local \
    .venv/bin/python -m pytest tests/test_auth_api.py -v

Environment: isolated test database (barnamehsaz-postgres-test, port 5434).
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

# Import app AFTER env vars are set
from app.main import app, _login_failures  # noqa: E402
from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.base import User, Membership, Organization, RefreshSession, AuditEvent  # noqa: E402
from app.core.password_utils import hash_password  # noqa: E402
from app.core.jwt_utils import hash_refresh_token  # noqa: E402

DEMO_ADMIN = "admin@demo.example"
DEMO_MGR = "employee01@demo.example"
DEMO_PASSWORD = "12345678"


def _login(client, email=DEMO_ADMIN, password=DEMO_PASSWORD):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def clean_state(db_session):
    """Reset auth state (users, refresh_sessions, audit_events, rate limiter) between tests."""
    # Wipe Phase 3 child tables first (FK order: deepest children first)
    from app.models.phase3 import (
        DomainAuditEvent, SharedOfferingApproval, WizardDraft,
        SubmissionComment, SubmissionRevision, Submission,
    )
    db_session.query(DomainAuditEvent).delete()
    db_session.query(SharedOfferingApproval).delete()
    db_session.query(WizardDraft).delete()
    db_session.query(SubmissionComment).delete()
    db_session.query(SubmissionRevision).delete()
    db_session.query(Submission).delete()
    # Wipe Phase 2 child tables first (FK order: deepest children first)
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
    # Wipe auth state (children first, then organizations)
    db_session.query(RefreshSession).delete()
    db_session.query(AuditEvent).delete()
    db_session.query(Membership).delete()
    db_session.query(User).delete()
    db_session.query(Organization).delete()
    db_session.commit()
    _seed_demo(db_session)
    _login_failures.clear()
    yield


@pytest.fixture(scope="module")
def db_session():
    """Fresh DB session for tests."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _seed_demo(db_session):
    org = Organization(name="دانشگاه آزمایشی نوین", slug="novin-university", timezone="Asia/Tehran")
    db_session.add(org)
    db_session.flush()
    org_id = org.id
    accounts = [
        (DEMO_ADMIN, "مدیر کل آزمایشی", "admin", True),
        (DEMO_MGR, "کارمند شماره ۱", "unit_manager", True),
    ]
    for email, name, role, must_change in accounts:
        user = User(email=email, password_hash=hash_password(DEMO_PASSWORD), full_name=name,
                    must_change_password=must_change, is_active=True, organization_id=org_id)
        db_session.add(user)
        db_session.flush()
        db_session.add(Membership(user_id=user.id, organization_id=org_id, role=role))
    db_session.commit()


class TestAuthAPI:
    """Authentication API integration tests."""

    def test_login_valid_credentials(self, client):
        """Login with valid credentials returns 200 and tokens."""
        data = _login(client)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == DEMO_ADMIN
        assert data["user"]["must_change_password"] is True

    def test_login_invalid_password(self, client):
        """Login with wrong password returns 401."""
        resp = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        """Login with non-existent email returns 401 (no user enumeration)."""
        resp = client.post("/auth/login", json={"email": "nonexistent@example.com", "password": DEMO_PASSWORD})
        assert resp.status_code == 401

    def test_register_without_auth_returns_401(self, client):
        """Register without authentication returns 401 (admin-only)."""
        resp = client.post("/auth/register", json={
            "email": "newuser@example.com", "password": "SecurePass123", "full_name": "New User"})
        assert resp.status_code == 401

    def test_register_with_unit_manager_returns_403(self, client):
        """Unit manager cannot register users (admin-only)."""
        data = _login(client, email=DEMO_MGR)
        token = data["access_token"]
        resp = client.post("/auth/register", json={
            "email": "newuser2@example.com", "password": "SecurePass123", "full_name": "New User 2"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_register_as_admin(self, client):
        """Admin can register a new user; backend forces must_change_password."""
        data = _login(client)
        token = data["access_token"]
        resp = client.post("/auth/register", json={
            "email": "newadmin@example.com", "password": "SecurePass123", "full_name": "New Admin"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "newadmin@example.com"
        assert resp.json()["must_change_password"] is True

    def test_forced_password_change_blocks_protected(self, client):
        """must_change_password=True blocks the protected endpoint (403) until changed."""
        data = _login(client)
        token = data["access_token"]
        user_id = data["user"]["id"]
        # Before change: gated endpoint is blocked
        blocked = client.get("/auth/protected", headers={"Authorization": f"Bearer {token}"})
        assert blocked.status_code == 403
        # Change the password
        ok = client.post("/auth/change-password", json={
            "current_password": DEMO_PASSWORD, "new_password": "NewSecurePass123!", "user_id": user_id},
            headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200
        # After change: gated endpoint is open
        opened = client.get("/auth/protected", headers={"Authorization": f"Bearer {token}"})
        assert opened.status_code == 200
        # Login works with the new password
        data2 = _login(client, password="NewSecurePass123!")
        assert data2["user"]["must_change_password"] is False

    def test_change_password_success(self, client):
        """User can change their own password and log in with the new one."""
        data = _login(client)
        token = data["access_token"]
        user_id = data["user"]["id"]
        resp = client.post("/auth/change-password", json={
            "current_password": DEMO_PASSWORD, "new_password": "NewSecurePass123!", "user_id": user_id},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        _login(client, password="NewSecurePass123!")
        # restore
        client.post("/auth/change-password", json={
            "current_password": "NewSecurePass123!", "new_password": DEMO_PASSWORD, "user_id": user_id},
            headers={"Authorization": f"Bearer {token}"})

    def test_change_password_wrong_current(self, client):
        """Changing password with wrong current password returns 400."""
        data = _login(client)
        token = data["access_token"]
        user_id = data["user"]["id"]
        resp = client.post("/auth/change-password", json={
            "current_password": "wrong", "new_password": "NewSecurePass123!", "user_id": user_id},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestRefreshRotation:
    """Real refresh/rotation/replay/logout integration tests (server-side)."""

    def test_refresh_success_and_rotation(self, client):
        """A valid refresh token is rotated; the old one becomes unusable."""
        data = _login(client)
        refresh1 = data["refresh_token"]
        # Rotate -> new pair
        r = client.post("/auth/refresh", json={"refresh_token": refresh1})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        refresh2 = body["refresh_token"]
        assert refresh2 != refresh1
        # The original refresh token is now revoked (DB holds only the hash)
        db = SessionLocal()
        try:
            h1 = hash_refresh_token(refresh1)
            h2 = hash_refresh_token(refresh2)
            row1 = db.query(RefreshSession).filter(RefreshSession.token_hash == h1).first()
            row2 = db.query(RefreshSession).filter(RefreshSession.token_hash == h2).first()
            assert row1 is not None and row1.revoked_at is not None
            assert row2 is not None and row2.revoked_at is None
            assert row1.family_id == row2.family_id  # same family
        finally:
            db.close()
        # The new token is still usable
        r2 = client.post("/auth/refresh", json={"refresh_token": refresh2})
        assert r2.status_code == 200

    def test_replay_of_old_refresh_token(self, client):
        """Replaying an already-rotated token is rejected and revokes the family."""
        data = _login(client)
        refresh1 = data["refresh_token"]
        # Rotate once (refresh1 is now revoked, refresh2 is live)
        r = client.post("/auth/refresh", json={"refresh_token": refresh1})
        refresh2 = r.json()["refresh_token"]
        # Replay the OLD token -> 401 and family revoked
        replay = client.post("/auth/refresh", json={"refresh_token": refresh1})
        assert replay.status_code == 401, replay.text
        # The still-live token in the same family is now also revoked
        r2 = client.post("/auth/refresh", json={"refresh_token": refresh2})
        assert r2.status_code == 401
        db = SessionLocal()
        try:
            h2 = hash_refresh_token(refresh2)
            row2 = db.query(RefreshSession).filter(RefreshSession.token_hash == h2).first()
            assert row2.revoked_at is not None  # family revoked
        finally:
            db.close()

    def test_logout_revokes_family(self, client):
        """Logout revokes the refresh family server-side; refresh then fails."""
        data = _login(client)
        refresh1 = data["refresh_token"]
        out = client.post("/auth/logout", json={"refresh_token": refresh1})
        assert out.status_code == 200
        assert out.json()["revoked_family"] is not None
        # After logout, the refresh token no longer works
        r = client.post("/auth/refresh", json={"refresh_token": refresh1})
        assert r.status_code == 401
        db = SessionLocal()
        try:
            h1 = hash_refresh_token(refresh1)
            row = db.query(RefreshSession).filter(RefreshSession.token_hash == h1).first()
            assert row.revoked_at is not None
        finally:
            db.close()

    def test_refresh_with_unknown_token(self, client):
        """An unknown / forged refresh token is rejected with 401."""
        resp = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client):
        """An access token cannot be used as a refresh token (type check)."""
        data = _login(client)
        resp = client.post("/auth/refresh", json={"refresh_token": data["access_token"]})
        assert resp.status_code == 401


class TestUnauthenticatedAndForbidden:
    """401 / 403 behavior."""

    def test_unauthenticated_access_returns_401(self, client):
        assert client.get("/auth/me").status_code == 401
        assert client.get("/auth/protected").status_code == 401

    def test_forbidden_role_returns_403(self, client):
        """Authenticated but insufficient role -> 403."""
        data = _login(client, email=DEMO_MGR)
        token = data["access_token"]
        resp = client.post("/auth/register", json={
            "email": "x@example.com", "password": "SecurePass123", "full_name": "X"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_refresh_unauthenticated_401(self, client):
        """Refresh without any valid token -> 401."""
        resp = client.post("/auth/refresh", json={"refresh_token": ""})
        assert resp.status_code in (401, 422)


class TestRateLimit:
    """Login rate limiting -> 429 after repeated failures."""

    def test_too_many_failed_logins_429(self, client):
        for _ in range(5):
            r = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": "bad"})
            assert r.status_code == 401
        # 6th attempt is rate-limited
        r = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": DEMO_PASSWORD})
        assert r.status_code == 429, f"expected 429, got {r.status_code}"


class TestPasswordChangeInvalidatesRefresh:
    """Changing the password revokes all that user's refresh sessions."""

    def test_change_password_revokes_refresh(self, client, db_session):
        data = _login(client)
        refresh1 = data["refresh_token"]
        user_id = data["user"]["id"]
        ok = client.post("/auth/change-password", json={
            "current_password": DEMO_PASSWORD, "new_password": "BrandNewPass123!", "user_id": user_id},
            headers={"Authorization": f"Bearer {data['access_token']}"})
        assert ok.status_code == 200
        # The pre-change refresh token is now revoked
        r = client.post("/auth/refresh", json={"refresh_token": refresh1})
        assert r.status_code == 401


class TestAccessTokenBehavior:
    """Access tokens are STATELESS JWTs: not immediately invalidated on
    logout / password change. They stay usable until their TTL
    (``access_token_expire_minutes``, 30 minutes by default).
    Only the *refresh* family is revoked server-side. Q4 point 3.

    These tests assert behavior *within the TTL window* (no sleep needed),
    so they pass regardless of the configured TTL value."""

    def test_access_token_still_valid_after_logout(self, client):
        data = _login(client)
        access = data["access_token"]
        refresh = data["refresh_token"]
        out = client.post("/auth/logout", json={"refresh_token": refresh})
        assert out.status_code == 200
        assert out.json()["revoked_family"] is not None
        # Old ACCESS token (issued before logout) still works: stateless.
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        # Refresh token is dead -> no new access can be minted.
        r = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401

    def test_access_token_still_valid_after_password_change(self, client):
        data = _login(client)
        access = data["access_token"]
        user_id = data["user"]["id"]
        ok = client.post("/auth/change-password", json={
            "current_password": DEMO_PASSWORD, "new_password": "AnotherPass!2026", "user_id": user_id},
            headers={"Authorization": f"Bearer {access}"})
        assert ok.status_code == 200
        # Old access token still valid (stateless, within TTL).
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        # Old refresh token revoked by the password change.
        r = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
        assert r.status_code == 401


def self_assert_no_secrets(meta: dict):
    """Audit metadata must never carry secrets."""
    blob = " ".join(str(v) for v in (meta or {}).values())
    assert DEMO_PASSWORD not in blob


class TestAuditTrail:
    """Q4 audit: login / login-failed / logout / change-password are recorded
    in the audit_events table. Secrets are NEVER written to audit metadata."""

    def test_login_event_recorded(self, client, db_session):
        data = _login(client)
        user_id = data["user"]["id"]
        rows = db_session.query(AuditEvent).filter(
            AuditEvent.action == "login", AuditEvent.user_id == user_id).all()
        assert len(rows) >= 1, "expected at least one 'login' audit event"
        for row in rows:
            self_assert_no_secrets(row.meta)

    def test_login_failed_event_recorded(self, client, db_session):
        r = client.post("/auth/login", json={"email": DEMO_ADMIN, "password": "totally-wrong"})
        assert r.status_code == 401
        user = db_session.query(User).filter(User.email == DEMO_ADMIN).first()
        rows = db_session.query(AuditEvent).filter(
            AuditEvent.action == "login_failed", AuditEvent.user_id == user.id).all()
        assert len(rows) >= 1, "expected a 'login_failed' audit event"
        for row in rows:
            self_assert_no_secrets(row.meta)

    def test_logout_event_recorded(self, client, db_session):
        data = _login(client)
        user_id = data["user"]["id"]
        out = client.post("/auth/logout", json={"refresh_token": data["refresh_token"]})
        assert out.status_code == 200
        rows = db_session.query(AuditEvent).filter(
            AuditEvent.action == "logout", AuditEvent.user_id == user_id).all()
        assert len(rows) >= 1, "expected a 'logout' audit event"
        for row in rows:
            self_assert_no_secrets(row.meta)

    def test_change_password_event_recorded(self, client, db_session):
        data = _login(client)
        user_id = data["user"]["id"]
        ok = client.post("/auth/change-password", json={
            "current_password": DEMO_PASSWORD, "new_password": "YetAnotherPass!9", "user_id": user_id},
            headers={"Authorization": f"Bearer {data['access_token']}"})
        assert ok.status_code == 200
        rows = db_session.query(AuditEvent).filter(
            AuditEvent.action == "change_password", AuditEvent.user_id == user_id).all()
        assert len(rows) >= 1, "expected a 'change_password' audit event"
        for row in rows:
            self_assert_no_secrets(row.meta)

    def test_audit_meta_never_contains_secrets(self, client, db_session):
        """No audit row's metadata may contain the raw password or any token."""
        data = _login(client)
        user_id = data["user"]["id"]
        rows = db_session.query(AuditEvent).filter(AuditEvent.user_id == user_id).all()
        assert len(rows) >= 1
        for row in rows:
            blob = " ".join(str(v) for v in (row.meta or {}).values())
            assert DEMO_PASSWORD not in blob, "raw password leaked into audit meta"
            assert data["access_token"] not in blob, "access token leaked into audit meta"
            assert data["refresh_token"] not in blob, "refresh token leaked into audit meta"
