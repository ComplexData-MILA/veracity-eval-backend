import logging
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC

from app.models.database.models import ClaimModel, ClaimStatus
from app.models.domain.claim import Claim
from app.repositories.base import BaseRepository
from app.repositories.interfaces.claim_repository import ClaimRepositoryInterface

logger = logging.getLogger(__name__)


class ClaimRepository(BaseRepository[ClaimModel, Claim], ClaimRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ClaimModel)

    def _to_model(self, claim: Claim) -> ClaimModel:
        return ClaimModel(
            id=claim.id,
            user_id=claim.user_id,
            claim_text=claim.claim_text,
            context=claim.context,
            batch_user_id=claim.batch_user_id,
            batch_post_id=claim.batch_post_id,
            language=claim.language,
            embedding=claim.embedding,
            status=ClaimStatus(claim.status).value,
        )

    def _to_domain(self, model: ClaimModel) -> Claim:
        return Claim(
            id=model.id,
            user_id=model.user_id,
            claim_text=model.claim_text,
            context=model.context,
            language=model.language,
            batch_user_id=model.batch_user_id,
            batch_post_id=model.batch_post_id,
            embedding=model.embedding,
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
        try:
            claim = await self.get(claim_id)
            if not claim:
                return None

            claim.status = status
            updated_claim = await self.update(claim)
            return updated_claim

        except Exception:
            logger.exception("Error updating claim status")
            raise

    async def get_claims_in_date_range(self, start_date: datetime, end_date: datetime, language: str) -> List[Claim]:
        stmt = select(self._model_class).where(
            and_(
                self._model_class.created_at >= start_date,
                self._model_class.created_at <= end_date,
                self._model_class.status == ClaimStatus.analyzed,
                self._model_class.language == language,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(claim) for claim in result.scalars().all()]
    
    async def get_monthly_claim_count(self, user_id: str) -> int:
        """Counts how many claims a user has created this month."""
        
        # Calculate the 1st of the current month
        now = datetime.now(UTC)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = (
            select(func.count())
            .select_from(ClaimModel)
            .where(
                ClaimModel.user_id == user_id,
                ClaimModel.created_at >= start_of_month
            )
        )
        
        result = await self._session.execute(query)
        return result.scalar_one()

    async def insert_many(self, claim: List[Claim]) -> List[Claim]:
        models = [self._to_model(claim) for claim in claim]
        self._session.add_all(models)
        await self._session.flush()  # get generated fields like id, created_at
        await self._session.commit()
        return [self._to_domain(model) for model in models]
