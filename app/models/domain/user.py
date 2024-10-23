from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from uuid import UUID


@dataclass
class User:
    id: UUID
    username: str
    email: str
    auth0_id: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    preferences: dict = None

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def is_authenticated(self) -> bool:
        return self.is_active
