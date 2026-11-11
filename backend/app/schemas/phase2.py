"""Phase 2 Pydantic schemas: Organization / Planning Cycle / Resources / Calendar.

All schemas are org-scoped: the client never supplies organization_id on
create (it is derived from the caller membership), and reads are scoped to
caller organization.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import date, datetime
from typing import Optional


_HHMM_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


def _hhmm_check(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    hh, mm = value.split(":")
    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        raise ValueError(f"{field_name}: invalid time of day {value!r}")
    return value


def _check_window(start: str, end: str) -> None:
    if end <= start:
        raise ValueError(f"end ({end}) must be strictly after start ({start})")


# ---------------- PlanningCycle ----------------
class PlanningCycleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Optional label; backend normalizes empty/blank to None (no 422).
    term: Optional[str] = Field(default=None, max_length=128)
    status: str = Field(default="draft", pattern="^(draft|open|submitted|reviewed|published)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @model_validator(mode="after")
    def normalize_term(self):
        if self.term is None:
            return self
        if self.term.strip() == "":
            self.term = None
        return self


class PlanningCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    term: Optional[str] = None
    status: str
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: datetime
    deleted_at: Optional[datetime] = None


# ---------------- Unit ----------------
class UnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str]


class CycleUnitCreate(BaseModel):
    unit_id: int
    responsible_user_id: Optional[int] = None


class CycleUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    unit_id: int
    responsible_user_id: Optional[int]


# ---------------- Resource ----------------
class ResourceCreate(BaseModel):
    kind: str = Field(pattern="^(room|instructor)$")
    name: str = Field(min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)
    capacity: Optional[int] = Field(default=None, ge=1)
    details: Optional[str] = None

    @model_validator(mode="after")
    def room_capacity_required(self):
        if self.kind == "room" and self.capacity is None:
            raise ValueError("capacity is required for room resources")
        return self


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str
    code: Optional[str]
    capacity: Optional[int]
    details: Optional[str]
    created_at: datetime


class ResourceAvailabilityCreate(BaseModel):
    cycle_id: int
    weekday: int = Field(ge=0, le=6)
    start_hhmm: str = Field(pattern=_HHMM_PATTERN)
    end_hhmm: str = Field(pattern=_HHMM_PATTERN)

    @model_validator(mode="after")
    def check_window(self):
        _check_window(self.start_hhmm, self.end_hhmm)
        return self


class ResourceAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    cycle_id: int
    weekday: int
    start_hhmm: str
    end_hhmm: str
    deleted_at: Optional[datetime] = None


class ResourceCommitmentCreate(BaseModel):
    cycle_id: int
    weekday: int = Field(ge=0, le=6)
    start_hhmm: str = Field(pattern=_HHMM_PATTERN)
    end_hhmm: str = Field(pattern=_HHMM_PATTERN)
    reason: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def check_window(self):
        _check_window(self.start_hhmm, self.end_hhmm)
        return self


class ResourceCommitmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    cycle_id: int
    weekday: int
    start_hhmm: str
    end_hhmm: str
    reason: Optional[str]


# ---------------- Cohort ----------------
class CohortCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entry_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    unit_id: int


class CohortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    entry_year: Optional[int]
    unit_id: int


class CycleCohortCreate(BaseModel):
    cycle_id: int
    expected_enrollment: int = Field(default=0, ge=0)


class CycleCohortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int
    cohort_id: int
    expected_enrollment: int


# ---------------- Course / Offering ----------------
class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str


class CourseOfferingCreate(BaseModel):
    course_id: int
    planning_cycle_id: int
    section: Optional[str] = Field(default=None, max_length=64)
    meetings_per_week: int = Field(default=1, ge=1)
    duration_minutes: int = Field(default=90, ge=1)
    required_room_capacity: Optional[int] = Field(default=None, ge=1)
    room_type: Optional[str] = Field(default=None, max_length=64)


class CourseOfferingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    planning_cycle_id: int
    section: Optional[str]
    meetings_per_week: int
    duration_minutes: int
    required_room_capacity: Optional[int]
    room_type: Optional[str]
    created_at: datetime


class OfferingUnitCreate(BaseModel):
    unit_id: int
    expected_enrollment: int = Field(default=0, ge=0)


class OfferingCohortCreate(BaseModel):
    cohort_id: int
    expected_enrollment: int = Field(default=0, ge=0)


class MeetingRequirementCreate(BaseModel):
    offering_id: int
    allowed_weekday_min: Optional[int] = Field(default=None, ge=0, le=6)
    allowed_weekday_max: Optional[int] = Field(default=None, ge=0, le=6)
    start_window_hhmm: Optional[str] = Field(default=None, pattern=_HHMM_PATTERN)
    end_window_hhmm: Optional[str] = Field(default=None, pattern=_HHMM_PATTERN)

    @model_validator(mode="after")
    def check_range(self):
        if (self.allowed_weekday_min is not None and self.allowed_weekday_max is not None
                and self.allowed_weekday_min > self.allowed_weekday_max):
            raise ValueError("allowed_weekday_min must be <= allowed_weekday_max")
        if self.start_window_hhmm and self.end_window_hhmm:
            _check_window(self.start_window_hhmm, self.end_window_hhmm)
        return self


class MeetingRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offering_id: int
    allowed_weekday_min: Optional[int]
    allowed_weekday_max: Optional[int]
    start_window_hhmm: Optional[str]
    end_window_hhmm: Optional[str]
