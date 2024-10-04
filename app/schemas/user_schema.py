from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    username: str
    email: EmailStr


class UserRead(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    auth0_id: str
    created_at: datetime
    last_login: datetime

    model_config = ConfigDict(from_attributes=True)
