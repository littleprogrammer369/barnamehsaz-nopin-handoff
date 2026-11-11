from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.database import Base, engine

settings = get_settings()

app = FastAPI(
    title="Programmer Novin API",
    description="برنامه‌ساز نوین — API Facility",
    version="1.0.0",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Wire in Phase 2 router
# -----------------------------
# In-memory login rate limiter
# -----------------------------
from collections import defaultdict, deque
import time as _time

_RATE_LIMIT_MAX_FAILURES = 5
_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_login_failures: dict[str, deque] = defaultdict(deque)


def _rate_limit_key(request_client) -> str:
    return getattr(request_client, "host", "unknown") or "unknown"


def check_login_rate_limit(key: str) -> None:
    """Raise 429 if the key exceeded the failure budget inside the window."""
    now = _time.time()
    window = _login_failures[key]
    while window and now - window[0] > _RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _RATE_LIMIT_MAX_FAILURES:
        from fastapi import HTTPException, status as _st
        raise HTTPException(
            status_code=_st.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts; retry later",
        )


def record_login_failure(key: str) -> None:
    _login_failures[key].append(_time.time())


def clear_login_failures(key: str) -> None:
    _login_failures[key] = deque()


def reset_rate_limit_store() -> None:
    """Test helper: wipe the in-memory rate-limit store."""
    _login_failures.clear()


def _client_ip(request: Request) -> str:
    """Best-effort client IP (X-Forwarded-For aware, falls back to socket)."""
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _audit(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    ip: str = "unknown",
    meta: Optional[dict] = None,
) -> None:
    """Write a server-side audit row (Q4).

    Records who/what/where for security-relevant actions. **Secrets
    (passwords, OTPs, tokens) are never persisted.** This commits its own
    transaction, so call it *after* the caller's own commit has finished.
    """
    event = AuditEvent(
        action=action,
        user_id=user_id,
        actor_user_id=actor_user_id,
        ip=ip,
        meta=meta or {},
        created_at=_now_utc(),
    )
    db.add(event)
    db.commit()

@app.get("/")
def root():
    return {
        "service": "برنامه‌ساز نوین",
        "api_prefix": settings.api_prefix,
        "env": settings.app_env,
        "status": "operational",
    }

@app.on_event("startup")
def startup():
    if settings.app_env in ("development", "test"):
        Base.metadata.create_all(bind=engine)

# ===============================
# Authentication endpoints (Phase 1)
# ===============================
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.core.config import get_settings
from app.core.password_utils import hash_password, verify_password
from app.core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    new_family_id,
    REFRESH_TOKEN_TTL_DAYS,
)
from app.schemas.auth import UserCreate, UserLogin, UserResponse, RefreshRequest, LogoutRequest, ChangePasswordRequest
from app.models.base import User, Membership, Organization, RefreshSession, AuditEvent
from app.routers.phase2 import router as phase2_router
from app.routers.phase3 import router as phase3_router
from app.routers.phase4 import router as phase4_router
from app.routers.export import router as export_router  # Phase 6 export / publish

app.include_router(phase2_router)  # Phase 2
app.include_router(phase3_router)  # Phase 3
app.include_router(phase4_router)  # Phase 4
app.include_router(export_router)  # Phase 6 export / publish

settings = get_settings()
o2u = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

REFRESH_UNAUTHORIZED = {
    "status_code": 401,
    "headers": {"WWW-Authenticate": "Bearer"},
}


def _now_utc() -> _dt:
    """Current UTC time. DB columns are naive (DateTime without tz), so we
    store/compare naive UTC to avoid aware-vs-naive comparison errors."""
    return _dt.utcnow()


def get_current_user(token: str = Depends(o2u), db: Session = Depends(get_db)):
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type", headers={"WWW-Authenticate": "Bearer"})
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_role(required_role: str):
    """Dependency: require a specific role (admin or unit_manager)."""

    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        membership = (
            db.query(Membership)
            .filter(Membership.user_id == current_user.id)
            .filter(Membership.role == required_role)
            .first()
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker


def require_password_changed(current_user: User = Depends(get_current_user)):
    """Gate: block access if user must change password first."""
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing this endpoint",
        )
    return current_user


def create_test_accounts(db: Session):
    """Idempotent demo-account seed. Only runs in development/test (callers
    must check the guard). Creates the organization if missing, then the 6
    demo accounts, each linked to it and to a membership row."""
    existing = db.query(User).filter(User.email.like("%@demo.example")).count()
    if existing > 0:
        return
    org = db.query(Organization).filter(Organization.slug == "novin-university").first()
    if org is None:
        org = Organization(name="دانشگاه آزمایشی نوین", slug="novin-university", timezone="Asia/Tehran")
        db.add(org)
        db.flush()
    org_id = org.id
    accounts = [
        ("admin@demo.example", "مدیر کل آزمایشی", "admin", True),
        ("employee01@demo.example", "کارمند شماره ۱", "unit_manager", True),
        ("employee02@demo.example", "کارمند شماره ۲", "unit_manager", True),
        ("employee03@demo.example", "کارمند شماره ۳", "unit_manager", True),
        ("employee04@demo.example", "کارمند شماره ۴", "unit_manager", True),
        ("employee05@demo.example", "کارمند شماره ۵", "unit_manager", True),
    ]
    for email, name, role, must_change in accounts:
        user = User(email=email, password_hash=hash_password("12345678"), full_name=name,
                    must_change_password=must_change, is_active=True, organization_id=org_id)
        db.add(user); db.flush()
        db.add(Membership(user_id=user.id, role=role, organization_id=org_id))
    db.commit()

@app.post("/auth/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Register a new user. Requires admin role (no public registration)."""
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    org = db.query(Organization).first()
    if org is None:
        org = Organization(name="دانشگاه آزمایشی نوین", slug="novin-university", timezone="Asia/Tehran")
        db.add(org); db.flush()
    user = User(email=user_data.email, password_hash=hash_password(user_data.password), full_name=user_data.full_name,
                must_change_password=True, is_active=True, organization_id=org.id)
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login")
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = _rate_limit_key(request.client)
    ip = _client_ip(request)
    check_login_rate_limit(client_ip)
    user = db.query(User).filter(User.email == user_data.email).first()
    if user is None:
        record_login_failure(client_ip)
        _audit(db, "login_failed", user_id=None, ip=ip,
               meta={"email": user_data.email, "reason": "unknown_email"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not verify_password(user_data.password, user.password_hash):
        record_login_failure(client_ip)
        _audit(db, "login_failed", user_id=user.id, ip=ip,
               meta={"email": user_data.email, "reason": "bad_password"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    clear_login_failures(client_ip)
    access_token = create_access_token(data={"sub": str(user.id)})
    family_id = new_family_id()
    refresh_token = _issue_refresh_session(db, user, family_id)
    _audit(db, "login", user_id=user.id, ip=ip, meta={"family_id": family_id})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "must_change_password": user.must_change_password,
        },
    }


def _issue_refresh_session(db: Session, user: User, family_id: str) -> str:
    """Create a refresh token, persist only its hash, and return the token."""
    refresh_token = create_refresh_token(data={"sub": str(user.id)}, family_id=family_id)
    expires_at = _now_utc() + _td(days=REFRESH_TOKEN_TTL_DAYS)
    db.add(RefreshSession(
        token_hash=hash_refresh_token(refresh_token),
        user_id=user.id,
        family_id=family_id,
        expires_at=expires_at,
    ))
    db.commit()
    return refresh_token


def _revoke_family(db: Session, family_id: str) -> None:
    """Revoke every live refresh session of a token family (server-side)."""
    now = _now_utc()
    rows = db.query(RefreshSession).filter(
        RefreshSession.family_id == family_id,
        RefreshSession.revoked_at.is_(None),
    ).all()
    for row in rows:
        row.revoked_at = now
    db.commit()


def _decode_refresh(db: Session, raw_token: str, expected_family: Optional[str] = None):
    """Validate a refresh token and return (user, payload, session_row).

    Raises HTTPException(401) with a descriptive detail when the token cannot
    be used. A replay (already-revoked token) additionally revokes the whole
    family on the server.
    """
    payload = decode_token(raw_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token", headers=REFRESH_UNAUTHORIZED["headers"])
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload", headers=REFRESH_UNAUTHORIZED["headers"])
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive", headers=REFRESH_UNAUTHORIZED["headers"])
    thash = hash_refresh_token(raw_token)
    row = db.query(RefreshSession).filter(RefreshSession.token_hash == thash).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown refresh token", headers=REFRESH_UNAUTHORIZED["headers"])
    now = _now_utc()
    if row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired", headers=REFRESH_UNAUTHORIZED["headers"])
    if row.revoked_at is not None:
        # REPLAY: this token was already rotated/revoked. Revoke the whole family.
        _revoke_family(db, row.family_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token replay detected; family revoked", headers=REFRESH_UNAUTHORIZED["headers"])
    if expected_family is not None and row.family_id != expected_family:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token family mismatch", headers=REFRESH_UNAUTHORIZED["headers"])
    return user, payload, row


@app.post("/auth/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate a refresh token. The previous token is revoked immediately.

    - A valid, non-revoked token is exchanged for a fresh access+refresh pair;
      the refresh token that was just presented is marked revoked so it cannot
      be reused.
    - A replay of an already-rotated token revokes the whole family and
      returns 401.
    - Expiry / tampering / unknown tokens all return 401.
    """
    user, payload, row = _decode_refresh(db, body.refresh_token)
    # Rotate: revoke this exact row, then issue the next one in the same family
    row.revoked_at = _now_utc()
    db.commit()
    new_refresh = _issue_refresh_session(db, user, family_id=row.family_id)
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@app.post("/auth/logout")
def logout(body: LogoutRequest, request: Request, db: Session = Depends(get_db)):
    """Revoke the refresh family server-side.

    The optional ``refresh_token`` in the body is decoded and its whole family
    is revoked, which is the real server-side invalidation. Clearing the
    browser's memory alone is NOT sufficient, so clients should always send
    the token they still hold here. When the token is absent, still return 200
    so the client can finish its own cleanup; ``revoked_family`` is null in
    that case.
    """
    ip = _client_ip(request)
    revoked_family: Optional[str] = None
    if body.refresh_token:
        try:
            user, payload, row = _decode_refresh(db, body.refresh_token)
            _revoke_family(db, row.family_id)
            revoked_family = row.family_id
            _audit(db, "logout", user_id=user.id, ip=ip,
                   meta={"family_id": row.family_id})
        except HTTPException:
            # Unknown / expired / replayed token: nothing valid to revoke,
            # but still answer 200 so the client can complete logout.
            pass
    return {"status": "ok", "revoked_family": revoked_family}


@app.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password. User can only change their own password unless admin.

    On success all refresh sessions of the user are revoked (the password
    changed, so every previously issued token family is invalidated).
    """
    current_password = body.current_password
    new_password = body.new_password
    user_id = body.user_id
    if current_user.id != user_id:
        membership = (
            db.query(Membership)
            .filter(Membership.user_id == current_user.id)
            .filter(Membership.role == "admin")
            .first()
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change another user's password",
            )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(new_password) < settings.pass_min_length:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"New password must be at least {settings.pass_min_length} characters")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.query(RefreshSession).filter(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None),
    ).update({"revoked_at": _now_utc()}, synchronize_session=False)
    db.commit()
    _audit(db, "change_password", user_id=user.id, actor_user_id=current_user.id,
           ip=_client_ip(request),
           meta={"admin_acted": current_user.id != user.id})
    return {"status": "ok", "message": "Password changed successfully"}


@app.get("/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@app.get("/auth/protected")
def protected(user: User = Depends(require_password_changed)):
    """Representative protected endpoint gated by the password-change check.

    An authenticated user with must_change_password=True gets 403 here; the
    gate opens after a successful password change. This is the endpoint the
    forced-password-change integration test is exercised against.
    """
    return {"message": "You reached a protected endpoint", "user_id": user.id}


@app.on_event("startup")
def seed_demo_accounts():
    """Seed demo accounts on startup (development/test only)."""
    if settings.app_env in ("development", "test"):
        db = SessionLocal()
        try:
            create_test_accounts(db)
        finally:
            db.close()
