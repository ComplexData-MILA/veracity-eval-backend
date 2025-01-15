from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.models import ClaimModel, ClaimStatus
from app.models.domain.claim import Claim
from app.repositories.base import BaseRepository
from app.repositories.interfaces.claim_repository import ClaimRepositoryInterface


class ClaimRepository(BaseRepository[ClaimModel, Claim], ClaimRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ClaimModel)

    def _to_model(self, claim: Claim) -> ClaimModel:
        return ClaimModel(
            id=claim.id,
            user_id=claim.user_id,
            claim_text=claim.claim_text,
            context=claim.context,
            language=claim.language,
            status=ClaimStatus(claim.status).value,
        )

    def _to_domain(self, model: ClaimModel) -> Claim:
        return Claim(
            id=model.id,
            user_id=model.user_id,
            claim_text=model.claim_text,
            context=model.context,
            language=model.language,
            status=ClaimStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_user_claims(
        self, user_id: UUID, status: Optional[ClaimStatus] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Claim], int]:
        """Get claims for a user with pagination."""
        query = select(self._model_class).where(self._model_class.user_id == user_id)

        if status:
            query = query.where(self._model_class.status == status)

        count_query = select(func.count()).select_from(self._model_class).where(self._model_class.user_id == user_id)
        if status:
            count_query = count_query.where(self._model_class.status == status)

        total = await self._session.scalar(count_query)

        query = query.order_by(self._model_class.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        claims = [self._to_domain(model) for model in result.scalars().all()]

        return claims, total

    async def update_status(self, claim_id: UUID, status: ClaimStatus) -> Optional[Claim]:
        """Update claim status."""
        claim = await self.get(claim_id)
        if not claim:
            return None

        claim.status = status.value
        return await self.update(claim)
