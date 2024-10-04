from uuid import UUID
from datetime import datetime
from app.models.domain.claim import Claim
from uuid import uuid4
from app.schemas.claim_schema import ClaimCreate


class ClaimService:
    def create_claim(self, claim_create: ClaimCreate) -> Claim:
        return Claim(
            id=uuid4(),
            user_id=claim_create.user_id,
            claim_text=claim_create.claim_text,
            context=claim_create.context,
            created_at=datetime.now(),
        )

    def get_claim(self, claim_id: UUID) -> Claim:
        # In a real implementation, this would fetch from a database
        pass
