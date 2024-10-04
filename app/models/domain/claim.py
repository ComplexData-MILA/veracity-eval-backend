from uuid import UUID
from datetime import datetime


class Claim:
    def __init__(self, id: UUID, user_id: UUID, claim_text: str, context: str, created_at: datetime):
        self.id = id
        self.user_id = user_id
        self.claim_text = claim_text
        self.context = context
        self.created_at = created_at
