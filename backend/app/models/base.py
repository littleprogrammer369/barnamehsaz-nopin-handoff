from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Index, UniqueConstraint, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base
from datetime import datetime, timezone
import uuid


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tehran")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_organizations_slug', 'slug', unique=True),
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="user")

    __table_args__ = (
        Index('ix_users_email', 'email', unique=True),
        Index('ix_users_organization_id', 'organization_id'),
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    # Optional: for unit_manager role, this FK points to the managed unit
    unit_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("units.id"), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")

    __table_args__ = (
        Index('ix_memberships_user_organization', 'user_id', 'organization_id'),
        Index('ix_memberships_unit_id', 'unit_id'),
        # Constraint: unit_id NOT NULL iff role='unit_manager'
        CheckConstraint(
            "(role = 'unit_manager' AND unit_id IS NOT NULL) OR (role != 'unit_manager' AND unit_id IS NULL)",
            name="ck_memberships_unit_role_consistency"
        ),
    )



class RefreshSession(Base):
    """Server-side record for a refresh token.

    Security model (Q4 / Bearer-only closeout):
    - Only a SHA-256 hash of the refresh token is stored (``token_hash``),
      never the raw token.
    - ``family_id`` groups the rotations of a single login session.
    - On every successful rotation the previous row is marked revoked; a
      replay of an already-rotated token revokes the whole family.
    - On logout the family is revoked on the server (clearing browser
      memory alone is not sufficient).
    """

    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SHA-256 hex digest of the refresh token (64 chars)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # When the row was revoked by rotation / replay / logout / password change
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_refresh_sessions_user_id', 'user_id'),
        Index('ix_refresh_sessions_family_id', 'family_id'),
    )


class AuditEvent(Base):
    """Server-side audit trail for security-relevant actions (Q4).

    Records *who / what / when / where* for login, login-failure, logout and
    password-change events. **Secrets (passwords, OTPs, access/refresh
    tokens) are never persisted in this table.**
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # e.g. "login", "login_failed", "logout", "change_password"
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # When an admin acts on another user's password, the actor
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True, index=True)

    __table_args__ = (
        Index('ix_audit_events_user_id', 'user_id'),
        Index('ix_audit_events_created_at', 'created_at'),
        Index('ix_audit_events_organization_id', 'organization_id'),
    )

