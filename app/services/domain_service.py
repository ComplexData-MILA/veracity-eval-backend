from uuid import UUID, uuid4
from typing import Optional, Tuple
from datetime import datetime, UTC

from app.models.domain.domain import Domain
from app.repositories.implementations.domain_repository import DomainRepository
from app.core.exceptions import NotFoundException
from app.core.utils.url import normalize_domain_name


class DomainService:
    def __init__(self, domain_repository: DomainRepository):
        self._domain_repo = domain_repository

    async def create_domain(
        self,
        domain_name: str,
        credibility_score: float,
        is_reliable: bool,
        description: Optional[str] = None,
    ) -> Domain:
        normalized_name = normalize_domain_name(domain_name)

        domain = Domain(
            id=uuid4(),
            domain_name=normalized_name,
            credibility_score=credibility_score,
            is_reliable=is_reliable,
            description=description,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        return await self._domain_repo.create(domain)

    async def get_domain(self, domain_id: UUID) -> Domain:
        domain = await self._domain_repo.get(domain_id)
        if not domain:
            raise NotFoundException("Domain not found")
        return domain

    async def get_or_create_domain(self, domain_name: str) -> Tuple[Domain, bool]:
        return await self._domain_repo.get_or_create(domain_name)

    async def update_domain(
        self,
        domain_id: UUID,
        credibility_score: Optional[float] = None,
        is_reliable: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> Domain:
        domain = await self.get_domain(domain_id)

        if credibility_score is not None:
            domain.credibility_score = credibility_score
        if is_reliable is not None:
            domain.is_reliable = is_reliable
        if description is not None:
            domain.description = description

        domain.updated_at = datetime.now(UTC)
        return await self._domain_repo.update(domain)
