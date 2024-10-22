from uuid import UUID
from datetime import datetime


class ClaimConversation:
    def __init__(
        self,
        id: UUID,
        conversation_id: UUID,
        claim_id: UUID,
        start_time: datetime,
        end_time: datetime = None,
        status: str = "active",
    ):
        self.id = id
        self.conversation_id = conversation_id
        self.claim_id = claim_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
