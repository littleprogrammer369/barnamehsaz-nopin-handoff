from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(min_length=1, description="User's full name")
    must_change_password: bool = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    must_change_password: bool
    created_at: datetime


class MembershipCreate(BaseModel):
    user_id: int
    role: str = Field(pattern="^(admin|unit_manager)$", description="Role: admin or unit_manager")


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    created_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, description="Current refresh token (will be rotated)")


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token to revoke on the server. Omit to only clear the client side.",
    )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, description="New password (min 8 chars)")
    user_id: int = Field(description="The user whose password is being changed. Normally self.")


