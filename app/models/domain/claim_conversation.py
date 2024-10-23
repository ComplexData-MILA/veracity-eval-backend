from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.database.models.conversation import ConversationStatus


@dataclass
class ClaimConversation:
    def __init__(
        self,
        id: UUID,
        conversation_id: UUID,
        claim_id: UUID,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        status: ConversationStatus = ConversationStatus.ACTIVE,
    ):
        self.id = id
        self.conversation_id = conversation_id
        self.claim_id = claim_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
