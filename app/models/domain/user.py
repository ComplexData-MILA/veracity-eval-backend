from uuid import UUID
from datetime import datetime


class User:
    def __init__(self, id: UUID, username: str, email: str, created_at: datetime, last_login: datetime):
        self.id = id
        self.username = username
        self.email = email
        self.created_at = created_at
        self.last_login = last_login
