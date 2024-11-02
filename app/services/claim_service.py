from datetime import datetime, UTC
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from app.models.database.models import ClaimStatus
from app.models.domain.claim import Claim
from app.repositories.implementations.claim_repository import ClaimRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException


class ClaimService:
    def __init__(self, claim_repository: ClaimRepository):
        self._claim_repo = claim_repository

    async def create_claim(self, user_id: UUID, claim_text: str, context: str) -> Claim:
        """Create a new claim."""
        now = datetime.now(UTC)
        claim = Claim(
            id=uuid4(),
            user_id=user_id,
            claim_text=claim_text,
            context=context,
            status=ClaimStatus.pending,
            created_at=now,
            updated_at=now,
        )
        return await self._claim_repo.create(claim)

    async def update_claim_status(self, claim_id: UUID, status: ClaimStatus, user_id: UUID) -> Claim:
        """Update claim status."""
        claim = await self.get_claim(claim_id, user_id)
        claim.status = status
        claim.updated_at = datetime.now(UTC)
        return await self._claim_repo.update(claim)

    async def get_claim(self, claim_id: UUID, user_id: Optional[UUID] = None) -> Claim:
        """Get a claim and optionally verify ownership."""
        claim = await self._claim_repo.get(claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        if user_id and claim.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this claim")

        return claim

    async def list_user_claims(
        self, user_id: UUID, status: Optional[ClaimStatus] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Claim], int]:
        """List claims for a user with pagination."""
        return await self._claim_repo.get_user_claims(user_id=user_id, status=status, limit=limit, offset=offset)
