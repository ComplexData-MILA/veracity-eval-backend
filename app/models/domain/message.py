from uuid import UUID
from datetime import datetime
from typing import Optional


class Message:
    def __init__(
        self,
        id: UUID,
        conversation_id: UUID,
        sender_type: str,
        content: str,
        timestamp: datetime,
        claim_id: Optional[UUID] = None,
        analysis_id: Optional[UUID] = None,
    ):
        self.id = id
        self.conversation_id = conversation_id
        self.sender_type = sender_type
        self.content = content
        self.timestamp = timestamp
        self.claim_id = claim_id
        self.analysis_id = analysis_id
