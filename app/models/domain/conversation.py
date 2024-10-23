from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from typing import Optional, List


@dataclass
class Conversation:
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        status: str = "active",
        claim_conversations: Optional[List[UUID]] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.claim_conversations = claim_conversations or []
