from typing import Optional, Tuple
from uuid import uuid4
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.url import normalize_domain_name
from app.models.database.models import DomainModel
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

    async def get_or_create(self, domain_name: str) -> Tuple[Domain, bool]:
        """Get existing domain or create new one."""
        normalized_name = normalize_domain_name(domain_name)

        domain = await self.get_by_name(normalized_name)
        if domain:
            return domain, False

        new_domain = Domain(
            id=uuid4(),
            domain_name=normalized_name,
            credibility_score=None,
            is_reliable=False,
            description=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_domain = await self.create(new_domain)
        return created_domain, True
