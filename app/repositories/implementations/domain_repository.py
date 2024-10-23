from typing import Optional, List, Tuple
from uuid import uuid4
from datetime import datetime, UTC
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.url import normalize_domain_name
from app.models.database.domain import DomainModel
from app.models.domain.domain import Domain
from app.repositories.base import BaseRepository
from app.repositories.interfaces.domain_repository import DomainRepositoryInterface


class DomainRepository(BaseRepository[DomainModel, Domain], DomainRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, DomainModel)

    def _to_model(self, domain: Domain) -> DomainModel:
        return DomainModel(
            id=domain.id,
            domain_name=domain.domain_name,
            credibility_score=domain.credibility_score,
            is_reliable=domain.is_reliable,
            description=domain.description,
        )

    def _to_domain(self, model: DomainModel) -> Domain:
        return Domain(
            id=model.id,
            domain_name=model.domain_name,
            credibility_score=model.credibility_score,
            is_reliable=model.is_reliable,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_name(self, domain_name: str) -> Optional[Domain]:
        """Get domain by normalized name."""
        normalized_name = normalize_domain_name(domain_name)
        query = select(self._model_class).where(self._model_class.domain_name == normalized_name)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def search(
        self,
        query: str,
        reliability_filter: Optional[bool] = None,
        min_credibility: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Domain], int]:
        """Search domains with filters."""
        base_query = select(self._model_class)
        filters = []

        if query:
            search_filter = or_(
                self._model_class.domain_name.ilike(f"%{query}%"), self._model_class.description.ilike(f"%{query}%")
            )
            filters.append(search_filter)

        if reliability_filter is not None:
            filters.append(self._model_class.is_reliable == reliability_filter)

        if min_credibility is not None:
            filters.append(self._model_class.credibility_score >= min_credibility)

        if filters:
            base_query = base_query.where(and_(*filters))

        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self._session.scalar(count_query)

        query = base_query.order_by(self._model_class.credibility_score.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        domains = [self._to_domain(model) for model in result.scalars().all()]

        return domains, total

    async def get_or_create(self, domain_name: str) -> Tuple[Domain, bool]:
        """Get existing domain or create new one."""
        normalized_name = normalize_domain_name(domain_name)

        # Try to get existing domain
        domain = await self.get_by_name(normalized_name)
        if domain:
            return domain, False

        # Create new domain with default values
        new_domain = Domain(
            id=uuid4(),
            domain_name=normalized_name,
            credibility_score=0.5,  # Default middle score
            is_reliable=False,  # Default to not reliable
            description=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_domain = await self.create(new_domain)
        return created_domain, True
