from uuid import UUID, uuid4
from typing import List, Optional, Tuple
from datetime import datetime, UTC

from app.models.domain.source import Source
from app.repositories.implementations.source_repository import SourceRepository
from app.services.domain_service import DomainService
from app.core.exceptions import NotFoundException
from app.core.utils.url import normalize_domain_name


class SourceService:
    def __init__(self, source_repository: SourceRepository, domain_service: DomainService):
        self._source_repo = source_repository
        self._domain_service = domain_service

    async def create_source(
        self,
        analysis_id: UUID,
        url: str,
        title: str,
        snippet: str,
        content: Optional[str] = None,
    ) -> Source:
        """Create a new source."""
        domain_name = normalize_domain_name(url)
        domain, _ = await self._domain_service.get_or_create_domain(domain_name)

        source = Source(
            id=uuid4(),
            analysis_id=analysis_id,
            url=url,
            title=title,
            snippet=snippet,
            domain_id=domain.id,
            content=content,
            credibility_score=domain.credibility_score,  # Use domain's score initially
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        return await self._source_repo.create(source)

    async def get_source(self, source_id: UUID, include_content: bool = False) -> Source:
        """Get source by ID."""
        source = await self._source_repo.get(source_id)
        if not source:
            raise NotFoundException("Source not found")
        return source

    async def get_analysis_sources(self, analysis_id: UUID, include_content: bool = False) -> List[Source]:
        """Get all sources for an analysis."""
        return await self._source_repo.get_by_analysis(analysis_id=analysis_id, include_content=include_content)

    async def get_domain_sources(self, domain_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Source], int]:
        """Get sources from a specific domain."""
        return await self._source_repo.get_by_domain(domain_id=domain_id, limit=limit, offset=offset)
