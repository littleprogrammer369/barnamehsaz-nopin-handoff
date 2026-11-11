"""Phase 2 routers: Organization-scoped CRUD for planning cycles, units,
resources + per-cycle availability/commitments, cohorts, courses, offerings,
and meeting requirements.

All endpoints:
- Auth-gated (Bearer access token via get_current_user).
- Org-scoped: organization_id is derived from the caller's membership, never
  from a client-supplied field.
- Write endpoints require admin or unit_manager; read endpoints require any
  authenticated user.
"""

from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.jwt_utils import decode_token
from app.core.password_utils import verify_password
from fastapi.security import OAuth2PasswordBearer
from app.core.config import get_settings

_settings = get_settings()
_o2u = OAuth2PasswordBearer(tokenUrl=f"{_settings.api_prefix}/auth/login", auto_error=False)


def get_current_user(token: str = Depends(_o2u), db: Session = Depends(get_db)):
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_password_changed(current_user: User = Depends(get_current_user)):
    if current_user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required before accessing this endpoint")
    return current_user
from app.models.base import User, Membership
from app.models.phase2 import (
    PlanningCycle,
    Unit,
    CycleUnit,
    Resource,
    ResourceAvailability,
    ResourceCommitment,
    Cohort,
    CycleCohort,
    Course,
    CourseOffering,
    OfferingUnit,
    OfferingCohort,
    MeetingRequirement,
)
from app.models.phase3 import DomainAuditEvent
from app.core.rbac import (
    require_admin, require_role, get_unit_for_user, check_unit_access, can_manage_resource, ROLE_ADMIN, ROLE_UNIT_MANAGER
)
from app.schemas.phase2 import (
    PlanningCycleCreate,
    PlanningCycleRead,
    UnitCreate,
    UnitRead,
    CycleUnitCreate,
    CycleUnitRead,
    ResourceCreate,
    ResourceRead,
    ResourceAvailabilityCreate,
    ResourceAvailabilityRead,
    ResourceCommitmentCreate,
    ResourceCommitmentRead,
    CohortCreate,
    CohortRead,
    CycleCohortCreate,
    CycleCohortRead,
    CourseCreate,
    CourseRead,
    CourseOfferingCreate,
    CourseOfferingRead,
    OfferingUnitCreate,
    OfferingCohortCreate,
    MeetingRequirementCreate,
    MeetingRequirementRead,
)

router = APIRouter(prefix="/phase2", tags=["phase2"])


class OfferingUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    offering_id: int
    unit_id: int
    expected_enrollment: int
    room_resource_id: Optional[int] = None
    instructor_resource_id: Optional[int] = None

class PlanningCycleUpdate(BaseModel):
    name: Optional[str] = None
    term: Optional[str] = Field(default=None, max_length=128)
    status: Optional[str] = Field(default=None,
                                  pattern="^(draft|open|submitted|reviewed|published)$")

    @model_validator(mode="after")
    def normalize_term(self):
        if self.term is None:
            return self
        if self.term.strip() == "":
            self.term = None
        return self


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    responsible_user_id: Optional[int] = None
    program_id: Optional[int] = None


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[int] = None


class CourseUpdate(BaseModel):
    code: Optional[str] = None
    title: Optional[str] = None
    credits: Optional[int] = None


class ResourceNominationRequest(BaseModel):
    """Q12: manager nominates the canonical room/instructor for a
    shared offering.  Only one unit row per offering may carry the
    nomination (the proposing unit); conflict → 409."""
    room_resource_id: Optional[int] = None
    instructor_resource_id: Optional[int] = None

    def validate_not_same(self):
        if (self.room_resource_id is not None
                and self.instructor_resource_id is not None
                and self.room_resource_id == self.instructor_resource_id):
            raise ValueError("room and instructor resources must be distinct")


class OfferingCohortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    offering_id: int
    cohort_id: int
    expected_enrollment: int


def _org_id_for(user: User, db: Session) -> int:
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization membership")
    return membership.organization_id


def _require_write_role(user: User, db: Session) -> None:
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.role.in_(["admin", "unit_manager"]))
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin or unit_manager role required")

# ---------------- PlanningCycles ----------------
def _normalize_cycle_input(name: str, term: Optional[str]) -> tuple[str, Optional[str]]:
    """Normalise cycle input values.

    ``name`` is trimmed; a blank (missing, empty, or whitespace-only) name is a
    422. ``term`` is *more forgiving*: a missing value, an empty string, only
    whitespace, or ``None`` is treated as "no label" and normalised to ``None``
    so the API never returns a 422 for a deliberately blank term.
    """
    name = name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Planning cycle name is required",
        )
    if term is None or str(term).strip() == "":
        term = None
    return name, term


@router.put("/planning-cycles/{cycle_id}", response_model=PlanningCycleRead)
def update_planning_cycle(
    cycle_id: int,
    body: PlanningCycleUpdate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Edit a planning cycle (name/term/status). Only admins can edit cycles."""
    org_id = _org_id_for(current_user, db)
    require_admin(current_user, db, org_id)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id,
        PlanningCycle.organization_id == org_id,
        PlanningCycle.deleted_at.is_(None),
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    if body.name is not None:
        name, _ = _normalize_cycle_input(body.name, None)
        existing = db.query(PlanningCycle).filter(
            PlanningCycle.organization_id == org_id,
            PlanningCycle.name == name,
            PlanningCycle.id != cycle_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409,
                                detail=f"Planning cycle named {name!r} already exists")
        cycle.name = name
    if body.term is not None:
        if str(body.term).strip() == "":
            cycle.term = None
        else:
            cycle.term = body.term.strip()
    if body.status is not None:
        allowed = {"draft", "open", "submitted", "reviewed", "published"}
        if body.status not in allowed:
            raise HTTPException(status_code=422,
                                detail="status must be one of: draft, open, submitted, reviewed, published")
        cycle.status = body.status
    db.commit()
    db.refresh(cycle)
    return cycle


@router.post("/planning-cycles", response_model=PlanningCycleRead, status_code=201)
def create_planning_cycle(
    body: PlanningCycleCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Create a planning cycle. Only admins can create cycles."""
    require_admin(current_user, db, _org_id_for(current_user, db))
    org_id = _org_id_for(current_user, db)
    name, term = _normalize_cycle_input(body.name, body.term)
    existing = db.query(PlanningCycle).filter(
        PlanningCycle.organization_id == org_id, PlanningCycle.name == name
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Planning cycle named {name!r} already exists")
    cycle = PlanningCycle(organization_id=org_id, name=name, term=term, **body.model_dump(exclude={"name", "term"}))
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/planning-cycles", response_model=List[PlanningCycleRead])
def list_planning_cycles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    return (
        db.query(PlanningCycle)
        .filter(PlanningCycle.organization_id == org_id)
        .filter(PlanningCycle.deleted_at.is_(None))
        .all()
    )


@router.get("/planning-cycles/{cycle_id}", response_model=PlanningCycleRead)
def get_planning_cycle(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id,
        PlanningCycle.organization_id == org_id,
        PlanningCycle.deleted_at.is_(None),
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    return cycle


@router.delete("/planning-cycles/{cycle_id}", status_code=204)
def delete_planning_cycle(
    cycle_id: int,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Soft-delete a planning cycle. Only admins can delete cycles."""
    org_id = _org_id_for(current_user, db)
    require_admin(current_user, db, org_id)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    # Soft-delete: mark deleted_at instead of physical removal so references remain intact.
    cycle.deleted_at = datetime.now(timezone.utc)
    db.add(
        DomainAuditEvent(
            action="planning_cycle_deleted",
            organization_id=org_id,
            actor_user_id=current_user.id,
            subject_type="planning_cycle",
            subject_id=cycle.id,
            detail={"name": cycle.name, "term": cycle.term},
        )
    )
    db.commit()
    return None




# ---------------- Units ----------------
@router.post("/units", response_model=UnitRead, status_code=201)
def create_unit(
    body: UnitCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    if db.query(Unit).filter(Unit.organization_id == org_id, Unit.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Unit named {body.name!r} already exists")
    unit = Unit(**body.model_dump(), organization_id=org_id)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/units", response_model=List[UnitRead])
def list_units(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    return db.query(Unit).filter(Unit.organization_id == org_id).all()


@router.put("/units/{unit_id}", response_model=UnitRead)
def update_unit(
    unit_id: int,
    body: UnitUpdate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Edit a unit (name/description/responsible_user_id/program_id)."""
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    unit = db.query(Unit).filter(
        Unit.id == unit_id, Unit.organization_id == org_id, Unit.deleted_at.is_(None)
    ).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if body.name is not None:
        existing = db.query(Unit).filter(
            Unit.organization_id == org_id, Unit.name == body.name, Unit.id != unit_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Unit named {body.name!r} already exists")
        unit.name = body.name
    if body.description is not None:
        unit.description = body.description
    if body.responsible_user_id is not None:
        unit.responsible_user_id = body.responsible_user_id
    if body.program_id is not None:
        unit.program_id = body.program_id
    db.commit()
    db.refresh(unit)
    return unit


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: int,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Soft-delete a unit by setting deleted_at (preserves audit history)."""
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    unit = db.query(Unit).filter(
        Unit.id == unit_id, Unit.organization_id == org_id, Unit.deleted_at.is_(None)
    ).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    # Check for any linked offerings/courses before archiving
    # If referenced, 409 conflict since we must preserve references
    # Here we archive anyway but record it; actual reference check would be in phase4
    unit.deleted_at = datetime.now(timezone.utc)
    db.add(
        DomainAuditEvent(
            action="unit_deleted",
            organization_id=org_id,
            actor_user_id=current_user.id,
            subject_type="unit",
            subject_id=unit.id,
            detail={"name": unit.name},
        )
    )
    db.commit()
    return None


# ---------------- CycleUnit join ----------------
@router.post("/planning-cycles/{cycle_id}/units", response_model=CycleUnitRead, status_code=201)
def add_unit_to_cycle(
    cycle_id: int,
    body: CycleUnitCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    unit = db.query(Unit).filter(Unit.id == body.unit_id, Unit.organization_id == org_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found in this organization")
    if db.query(CycleUnit).filter(CycleUnit.cycle_id == cycle_id, CycleUnit.unit_id == body.unit_id).first():
        raise HTTPException(status_code=409, detail="Unit already linked to this cycle")
    link = CycleUnit(cycle_id=cycle_id, unit_id=body.unit_id, responsible_user_id=body.responsible_user_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get("/planning-cycles/{cycle_id}/units", response_model=List[CycleUnitRead])
def list_cycle_units(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found")
    return db.query(CycleUnit).filter(CycleUnit.cycle_id == cycle_id).all()


# ---------------- Resources ----------------
@router.post("/resources", response_model=ResourceRead, status_code=201)
def create_resource(
    body: ResourceCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Create a resource (room or instructor).
    
    Permissions:
    - Rooms: admin-only
    - Instructors: admin and unit_manager
    """
    org_id = _org_id_for(current_user, db)
    
    # Check permissions based on resource kind
    can_manage_resource(current_user, db, org_id, body.kind)
    
    existing = db.query(Resource).filter(
        Resource.organization_id == org_id, Resource.kind == body.kind, Resource.name == body.name
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Resource {body.name!r} of kind {body.kind} already exists")
    res = Resource(**body.model_dump(), organization_id=org_id)
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@router.get("/resources", response_model=List[ResourceRead])
def list_resources(
    kind: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    q = db.query(Resource).filter(
        Resource.organization_id == org_id,
        Resource.deleted_at.is_(None)
    )
    if kind:
        q = q.filter(Resource.kind == kind)
    return q.all()


@router.put("/resources/{resource_id}", response_model=ResourceRead)
def update_resource(
    resource_id: int,
    body: ResourceUpdate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Edit a resource (name/type/capacity).
    
    Permissions:
    - Rooms: admin-only
    - Instructors: admin and unit_manager
    """
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(
        Resource.id == resource_id, Resource.organization_id == org_id, Resource.deleted_at.is_(None)
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Check permissions based on resource kind
    can_manage_resource(current_user, db, org_id, res.kind)
    
    if body.name is not None:
        existing = db.query(Resource).filter(
            Resource.organization_id == org_id,
            Resource.kind == res.kind,
            Resource.name == body.name,
            Resource.id != resource_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Resource {body.name!r} of kind {res.kind} already exists")
        res.name = body.name
    if body.type is not None:
        res.type = body.type
    if body.capacity is not None:
        res.capacity = body.capacity
    db.commit()
    db.refresh(res)
    return res


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(
    resource_id: int,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Soft-delete a resource by setting deleted_at.
    
    Permissions:
    - Rooms: admin-only
    - Instructors: admin and unit_manager
    """
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(
        Resource.id == resource_id, Resource.organization_id == org_id, Resource.deleted_at.is_(None)
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Check permissions based on resource kind
    can_manage_resource(current_user, db, org_id, res.kind)
    
    # Check referenced availability/commitments - soft-delete only if no active references
    has_avail = db.query(ResourceAvailability).filter(
        ResourceAvailability.resource_id == resource_id,
        ResourceAvailability.deleted_at.is_(None)
    ).first()
    if has_avail:
        raise HTTPException(status_code=409, detail="Cannot archive resource with active availability records")
    has_commit = db.query(ResourceCommitment).filter(
        ResourceCommitment.resource_id == resource_id,
        ResourceCommitment.deleted_at.is_(None)
    ).first()
    if has_commit:
        raise HTTPException(status_code=409, detail="Cannot archive resource with active commitments")
    res.deleted_at = datetime.now(timezone.utc)
    db.add(
        DomainAuditEvent(
            action="resource_deleted",
            organization_id=org_id,
            actor_user_id=current_user.id,
            subject_type="resource",
            subject_id=res.id,
            detail={"name": res.name, "kind": res.kind},
        )
    )
    db.commit()
    return None

# ---------------- ResourceAvailability ----------------
@router.post("/resources/{resource_id}/availability", response_model=ResourceAvailabilityRead, status_code=201)
def create_resource_availability(
    resource_id: int,
    body: ResourceAvailabilityCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(Resource.id == resource_id, Resource.organization_id == org_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found in this organization")
    avail = ResourceAvailability(**body.model_dump(), resource_id=resource_id)
    db.add(avail)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate availability window")
    db.refresh(avail)
    return avail


@router.get("/resources/{resource_id}/availability", response_model=List[ResourceAvailabilityRead])
def list_resource_availability(
    resource_id: int,
    cycle_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(Resource.id == resource_id, Resource.organization_id == org_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found in this organization")
    q = db.query(ResourceAvailability).filter(
        ResourceAvailability.resource_id == resource_id,
        ResourceAvailability.deleted_at.is_(None),
    )
    if cycle_id is not None:
        q = q.filter(ResourceAvailability.cycle_id == cycle_id)
    return q.all()


@router.delete("/resource-availability/{availability_id}", status_code=204)
def delete_resource_availability(
    availability_id: int,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    row = db.query(ResourceAvailability).filter(ResourceAvailability.id == availability_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Availability window not found")
    res = db.query(Resource).filter(Resource.id == row.resource_id, Resource.organization_id == org_id).first()
    if not res:
        raise HTTPException(status_code=403, detail="Resource does not belong to this organization")
    # Audit-safe soft-delete instead of physical removal.
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return None


# ---------------- ResourceCommitment ----------------
@router.post("/resources/{resource_id}/commitments", response_model=ResourceCommitmentRead, status_code=201)
def create_resource_commitment(
    resource_id: int,
    body: ResourceCommitmentCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(Resource.id == resource_id, Resource.organization_id == org_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found in this organization")
    commitment = ResourceCommitment(**body.model_dump(), resource_id=resource_id)
    db.add(commitment)
    db.commit()
    db.refresh(commitment)
    return commitment


@router.get("/resources/{resource_id}/commitments", response_model=List[ResourceCommitmentRead])
def list_resource_commitments(
    resource_id: int,
    cycle_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    res = db.query(Resource).filter(Resource.id == resource_id, Resource.organization_id == org_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found in this organization")
    q = db.query(ResourceCommitment).filter(ResourceCommitment.resource_id == resource_id)
    if cycle_id is not None:
        q = q.filter(ResourceCommitment.cycle_id == cycle_id)
    return q.all()


# ---------------- Cohorts ----------------
@router.post("/cohorts", response_model=CohortRead, status_code=201)
def create_cohort(
    body: CohortCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    unit = db.query(Unit).filter(Unit.id == body.unit_id, Unit.organization_id == org_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found in this organization")
    if db.query(Cohort).filter(Cohort.unit_id == body.unit_id, Cohort.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Cohort named {body.name!r} already exists for this unit")
    cohort = Cohort(**body.model_dump(), organization_id=org_id)
    db.add(cohort)
    db.commit()
    db.refresh(cohort)
    return cohort


@router.get("/cohorts", response_model=List[CohortRead])
def list_cohorts(
    unit_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    q = db.query(Cohort).filter(Cohort.organization_id == org_id)
    if unit_id is not None:
        q = q.filter(Cohort.unit_id == unit_id)
    return q.all()


# ---------------- Cohort cycle link ----------------
@router.post("/cohorts/{cohort_id}/cycle-links", response_model=CycleCohortRead, status_code=201)
def link_cohort_to_cycle(
    cohort_id: int,
    body: CycleCohortCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    cohort = db.query(Cohort).filter(Cohort.id == cohort_id, Cohort.organization_id == org_id).first()
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found in this organization")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == body.cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found in this organization")
    if db.query(CycleCohort).filter(CycleCohort.cycle_id == body.cycle_id, CycleCohort.cohort_id == cohort_id).first():
        raise HTTPException(status_code=409, detail="Cohort already linked to this cycle")
    link = CycleCohort(cycle_id=body.cycle_id, cohort_id=cohort_id, expected_enrollment=body.expected_enrollment)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ---------------- Courses ----------------
@router.post("/courses", response_model=CourseRead, status_code=201)
def create_course(
    body: CourseCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    if db.query(Course).filter(Course.organization_id == org_id, Course.code == body.code).first():
        raise HTTPException(status_code=409, detail=f"Course code {body.code!r} already exists")
    course = Course(**body.model_dump(), organization_id=org_id)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/courses", response_model=List[CourseRead])
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    return db.query(Course).filter(Course.organization_id == org_id).all()


@router.put("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    body: CourseUpdate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Edit a course (code/title/credits). Checks uniqueness of code."""
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    course = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == org_id, Course.deleted_at.is_(None)
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if body.code is not None:
        existing = db.query(Course).filter(
            Course.organization_id == org_id, Course.code == body.code, Course.id != course_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Course with code {body.code!r} already exists")
        course.code = body.code
    if body.title is not None:
        course.title = body.title
    if body.credits is not None:
        course.credits = body.credits
    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Soft-delete a course by setting deleted_at."""
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    course = db.query(Course).filter(
        Course.id == course_id, Course.organization_id == org_id, Course.deleted_at.is_(None)
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Check for active offerings
    has_offering = db.query(CourseOffering).filter(
        CourseOffering.course_id == course_id
    ).first()
    if has_offering:
        raise HTTPException(status_code=409, detail="Cannot archive course with active offerings")
    course.deleted_at = datetime.now(timezone.utc)
    db.add(
        DomainAuditEvent(
            action="course_deleted",
            organization_id=org_id,
            actor_user_id=current_user.id,
            subject_type="course",
            subject_id=course.id,
            detail={"code": course.code},
        )
    )
    db.commit()
    return None


# ---------------- Course Offerings ----------------
@router.post("/offerings", response_model=CourseOfferingRead, status_code=201)
def create_offering(
    body: CourseOfferingCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    course = db.query(Course).filter(Course.id == body.course_id, Course.organization_id == org_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found in this organization")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == body.planning_cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Planning cycle not found in this organization")
    existing = db.query(CourseOffering).filter(
        CourseOffering.course_id == body.course_id,
        CourseOffering.planning_cycle_id == body.planning_cycle_id,
        CourseOffering.section == body.section,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Offering with this course/cycle/section already exists")
    offering = CourseOffering(**body.model_dump())
    db.add(offering)
    db.commit()
    db.refresh(offering)
    return offering


@router.get("/offerings", response_model=List[CourseOfferingRead])
def list_offerings(
    planning_cycle_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List course offerings with unit isolation for unit managers.
    
    - Admin: sees all offerings in organization
    - Unit manager: sees only offerings where their unit participates (via OfferingUnit)
    """
    from app.core.rbac import get_user_role, ROLE_UNIT_MANAGER, get_unit_for_user
    
    org_id = _org_id_for(current_user, db)
    q = (
        db.query(CourseOffering)
        .join(PlanningCycle, CourseOffering.planning_cycle_id == PlanningCycle.id)
        .filter(PlanningCycle.organization_id == org_id)
    )
    if planning_cycle_id is not None:
        q = q.filter(CourseOffering.planning_cycle_id == planning_cycle_id)
    
    # Apply unit filtering for unit managers
    user_role = get_user_role(current_user.id, org_id, db)
    if user_role == ROLE_UNIT_MANAGER:
        user_unit_id = get_unit_for_user(current_user.id, org_id, db)
        if user_unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid unit manager configuration"
            )
        # Join with OfferingUnit to filter offerings
        q = (
            q.join(OfferingUnit, CourseOffering.id == OfferingUnit.offering_id)
            .filter(OfferingUnit.unit_id == user_unit_id)
            .distinct()
        )
    
    return q.all()


# ---------------- Offering joins ----------------
@router.post("/offerings/{offering_id}/units", response_model=OfferingUnitRead, status_code=201)
def link_offering_to_unit(
    offering_id: int,
    body: OfferingUnitCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=403, detail="Offering does not belong to this organization")
    unit = db.query(Unit).filter(Unit.id == body.unit_id, Unit.organization_id == org_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found in this organization")
    if db.query(OfferingUnit).filter(OfferingUnit.offering_id == offering_id, OfferingUnit.unit_id == body.unit_id).first():
        raise HTTPException(status_code=409, detail="Unit already linked to this offering")
    link = OfferingUnit(offering_id=offering_id, unit_id=body.unit_id, expected_enrollment=body.expected_enrollment)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.post("/offerings/{offering_id}/units/{unit_id}/resources",
             response_model=OfferingUnitRead, status_code=200)
def nominate_offering_resources(
    offering_id: int,
    unit_id: int,
    body: ResourceNominationRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    """Q12 resource nomination: set / clear the canonical room and
    instructor resource for one offering-unit row.

    Only the proposing unit's row may carry the nomination; a second
    row on the same offering carrying a nomination is rejected (409).
    """
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id,
        PlanningCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=403,
                            detail="Offering does not belong to this organization")
    link = db.query(OfferingUnit).filter(
        OfferingUnit.offering_id == offering_id,
        OfferingUnit.unit_id == unit_id).first()
    if not link:
        raise HTTPException(status_code=404,
                            detail="Unit not linked to this offering")
    if (body.room_resource_id is not None
            and body.instructor_resource_id is not None
            and body.room_resource_id == body.instructor_resource_id):
        raise HTTPException(status_code=422,
                            detail="room and instructor resources must be distinct")
    for rid in filter(None,
                      (body.room_resource_id, body.instructor_resource_id)):
        res = db.query(Resource).filter(
            Resource.id == rid, Resource.organization_id == org_id).first()
        if res is None:
            raise HTTPException(status_code=404,
                                detail=f"Resource {rid} not found")
    # Q12 invariant: a second connected unit row already nominated → conflict
    other_nominated = db.query(OfferingUnit).filter(
        OfferingUnit.offering_id == offering_id,
        OfferingUnit.unit_id != unit_id,
        OfferingUnit.room_resource_id.isnot(None)
    ).first()
    if other_nominated is not None:
        raise HTTPException(
            status_code=409,
            detail="Another unit on this offering already holds the resource "
                   "nomination; clear it first (single resource identity, 06)")
    link.room_resource_id = body.room_resource_id
    link.instructor_resource_id = body.instructor_resource_id
    db.commit()
    db.refresh(link)
    return link


@router.post("/offerings/{offering_id}/cohorts", response_model=OfferingCohortRead, status_code=201)
def link_offering_to_cohort(
    offering_id: int,
    body: OfferingCohortCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=403, detail="Offering does not belong to this organization")
    cohort = db.query(Cohort).filter(Cohort.id == body.cohort_id, Cohort.organization_id == org_id).first()
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found in this organization")
    if db.query(OfferingCohort).filter(OfferingCohort.offering_id == offering_id, OfferingCohort.cohort_id == body.cohort_id).first():
        raise HTTPException(status_code=409, detail="Cohort already linked to this offering")
    link = OfferingCohort(offering_id=offering_id, cohort_id=body.cohort_id, expected_enrollment=body.expected_enrollment)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ---------------- Meeting Requirement ----------------
@router.post("/meeting-requirements", response_model=MeetingRequirementRead, status_code=201)
def create_meeting_requirement(
    body: MeetingRequirementCreate,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
):
    _require_write_role(current_user, db)
    org_id = _org_id_for(current_user, db)
    offering = db.query(CourseOffering).filter(CourseOffering.id == body.offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=403, detail="Offering does not belong to this organization")
    if db.query(MeetingRequirement).filter(MeetingRequirement.offering_id == body.offering_id).first():
        raise HTTPException(status_code=409, detail="This offering already has a meeting requirement (one per offering)")
    req = MeetingRequirement(**body.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/meeting-requirements/{requirement_id}", response_model=MeetingRequirementRead)
def get_meeting_requirement(
    requirement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = _org_id_for(current_user, db)
    req = db.query(MeetingRequirement).filter(MeetingRequirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Meeting requirement not found")
    offering = db.query(CourseOffering).filter(CourseOffering.id == req.offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    cycle = db.query(PlanningCycle).filter(
        PlanningCycle.id == offering.planning_cycle_id, PlanningCycle.organization_id == org_id
    ).first()
    if not cycle:
        raise HTTPException(status_code=403, detail="Offering does not belong to this organization")
    return req

