from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    """Base Pydantic model for users."""

    email: EmailStr
    username: str
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for user creation - includes auth0_id."""

    auth0_id: str


class UserRead(UserBase):
    """Schema for reading user data - includes additional fields."""

    id: UUID
    auth0_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
