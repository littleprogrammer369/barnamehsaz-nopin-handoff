"""Role-based access control helpers.

Defines roles, permission checks, and user-unit mappings.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.models.base import User, Membership
from app.models.phase2 import Unit

# Role constants
ROLE_ADMIN = "admin"
ROLE_UNIT_MANAGER = "unit_manager"

VALID_ROLES = {ROLE_ADMIN, ROLE_UNIT_MANAGER}


def get_user_role(user_id: int, org_id: int, db: Session) -> Optional[str]:
    """Get the user's role in the organization.
    
    Returns role string or None if user not in org.
    """
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.organization_id == org_id
        )
        .first()
    )
    return membership.role if membership else None


def get_unit_for_user(user_id: int, org_id: int, db: Session) -> Optional[int]:
    """Get the unit_id managed by a unit_manager.
    
    Returns unit_id if user is a unit_manager in org, else None.
    """
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.organization_id == org_id,
            Membership.role == ROLE_UNIT_MANAGER
        )
        .first()
    )
    return membership.unit_id if membership else None


def require_role(user: User, db: Session, org_id: int, roles: list[str]) -> None:
    """Check that user has one of the required roles.
    
    Raises 403 Forbidden if user's role not in list.
    """
    user_role = get_user_role(user.id, org_id, db)
    if user_role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This operation requires one of: {', '.join(roles)}"
        )


def require_admin(user: User, db: Session, org_id: int) -> None:
    """Check that user is an admin.
    
    Raises 403 Forbidden if not admin.
    """
    require_role(user, db, org_id, [ROLE_ADMIN])


def require_unit_manager(user: User, db: Session, org_id: int) -> Optional[int]:
    """Check that user is a unit_manager and return their unit_id.
    
    Raises 403 Forbidden if not unit_manager.
    Returns the unit_id managed by user.
    """
    unit_id = get_unit_for_user(user.id, org_id, db)
    if unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires unit_manager role"
        )
    return unit_id


def check_unit_access(user: User, db: Session, org_id: int, target_unit_id: int) -> None:
    """Check that user can access target_unit_id.
    
    Admin can access any unit. Unit manager can only access their own unit.
    Raises 403 Forbidden if access denied.
    """
    user_role = get_user_role(user.id, org_id, db)
    
    if user_role == ROLE_ADMIN:
        return  # admin can access any unit
    
    if user_role == ROLE_UNIT_MANAGER:
        user_unit_id = get_unit_for_user(user.id, org_id, db)
        if user_unit_id != target_unit_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access data for your assigned unit"
            )
        return
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid user role"
    )


def can_manage_resource(user: User, db: Session, org_id: int, resource_kind: str) -> bool:
    """Check if user can create/edit/delete a resource of given kind.
    
    Admin can manage all resource kinds.
    Unit manager can only manage 'instructor' kind (rooms are admin-only).
    
    Returns True if allowed, raises 403 if denied.
    """
    user_role = get_user_role(user.id, org_id, db)
    
    if user_role == ROLE_ADMIN:
        return True  # admin can manage all kinds
    
    if user_role == ROLE_UNIT_MANAGER:
        if resource_kind == "instructor":
            return True  # unit_manager can manage instructors
        else:
            # unit_manager cannot manage rooms or other kinds
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unit managers cannot manage '{resource_kind}' resources. Only admins can manage rooms and other resource types."
            )
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid user role"
    )
def apply_unit_filter(user: User, db: Session, org_id: int, query, unit_id_column):
    """Apply unit-level filtering to a query based on user role.
    
    Admin: no filter (sees all)
    Unit manager: filter to only their managed unit
    
    Args:
        user: Current user
        db: Database session
        org_id: Organization ID
        query: SQLAlchemy query object
        unit_id_column: The column to filter on (e.g., Submission.unit_id)
    
    Returns:
        Filtered query
    """
    user_role = get_user_role(user.id, org_id, db)
    
    if user_role == ROLE_ADMIN:
        return query  # Admin sees all, no filter
    
    if user_role == ROLE_UNIT_MANAGER:
        user_unit_id = get_unit_for_user(user.id, org_id, db)
        if user_unit_id is None:
            # Invalid state: unit_manager with no unit_id
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )
        return query.filter(unit_id_column == user_unit_id)
    
    # Invalid role
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid user role"
    )

