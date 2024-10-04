from uuid import UUID
from datetime import datetime


class Conversation:
    def __init__(
        self, id: UUID, user_id: UUID, start_time: datetime, end_time: datetime = None, status: str = "active"
    ):
        self.id = id
        self.user_id = user_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
