from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from app.models.database.claim import ClaimStatus
from app.models.domain.claim import Claim


class ClaimRepositoryInterface(ABC):
    """Interface for claim repository operations."""

    @abstractmethod
    async def create(self, claim: Claim) -> Claim:
        """Create a new claim."""
        pass

    @abstractmethod
    async def get(self, claim_id: UUID) -> Optional[Claim]:
        """Get claim by ID."""
        pass

    @abstractmethod
    async def update(self, claim: Claim) -> Claim:
        """Update a claim."""
        pass

    @abstractmethod
    async def delete(self, claim_id: UUID) -> bool:
        """Delete a claim."""
        pass

    @abstractmethod
    async def get_user_claims(
        self, user_id: UUID, status: Optional[ClaimStatus] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Claim], int]:
        """Get claims for a user with pagination."""
        pass

    @abstractmethod
    async def update_status(self, claim_id: UUID, status: ClaimStatus) -> Optional[Claim]:
        """Update claim status."""
        pass
