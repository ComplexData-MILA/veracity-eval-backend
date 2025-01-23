import logging
from typing import List, Tuple
from uuid import UUID

from app.models.domain.source import Source
from app.repositories.implementations.source_repository import SourceRepository
from app.repositories.implementations.search_repository import SearchRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.services.domain_service import DomainService
from app.core.exceptions import NotFoundException, NotAuthorizedException

logger = logging.getLogger(__name__)


class SourceService:
    def __init__(
        self,
        source_repository: SourceRepository,
        domain_service: DomainService,
        analysis_repository: AnalysisRepository,
        search_repository: SearchRepository,
        claim_repository: ClaimRepository,
    ):
        self._source_repo = source_repository
        self._domain_service = domain_service
        self._analysis_repo = analysis_repository
        self._search_repo = search_repository
        self._claim_repo = claim_repository

    async def _check_analysis_access(self, search_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to the analysis."""
        
        search = await self._search_repo.get(search_id)
        if not search:
            raise NotFoundException("Search not found")

        analysis = await self._analysis_repo.get(search.analysis_id)
        if not analysis:
            raise NotFoundException("Analysis not found")

        claim = await self._claim_repo.get(analysis.claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        # User has access if they own the claim
        return claim.user_id == user_id

    async def get_source(self, source_id: UUID, user_id: UUID, include_content: bool = False) -> Source:
        """Get source by ID with authorization check."""
        source = await self._source_repo.get(source_id)
        if not source:
            raise NotFoundException("Source not found")

        if not await self._check_analysis_access(source.search_id, user_id):
            raise NotAuthorizedException("Not authorized to access this source")

        return source

    async def get_search_sources(
        self, search_id: UUID, user_id: UUID, include_content: bool = False
    ) -> List[Source]:
        """Get all sources for an analysis with authorization check."""
        logger.debug(f"Getting sources for search {search_id} for user {user_id}")

        if not await self._check_analysis_access(search_id, user_id):
            logger.warning(f"User {user_id} not authorized to access search {search_id}")
            raise NotAuthorizedException("Not authorized to access these sources")

        try:
            sources = await self._source_repo.get_by_search(
                search_id=search_id,
                include_domain=True,
            )
            logger.debug(f"Found {len(sources)} sources for search {search_id}")
            return sources
        except Exception as e:
            logger.error(f"Error getting sources for search {search_id}: {str(e)}")
            raise

    async def get_search_sources_without_auth_check(
        self, search_id: UUID, user_id: UUID, include_content: bool = False
    ) -> List[Source]:
        """Get all sources for an analysis without authorization check. Check should be done in getting searches."""
        logger.debug(f"Getting sources for search {search_id} for user {user_id}")

        try:
            sources = await self._source_repo.get_by_search(
                search_id=search_id,
                include_domain=True,
            )
            logger.debug(f"Found {len(sources)} sources for search {search_id}")
            return sources
        except Exception as e:
            logger.error(f"Error getting sources for search {search_id}: {str(e)}")
            raise

    async def get_domain_sources(
        self, domain_id: UUID, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Source], int]:
        """Get sources from a specific domain with pagination and authorization check."""
        domain = await self._domain_service.get_domain(domain_id)
        if not domain:
            raise NotFoundException("Domain not found")

        # Get all sources for the domain
        #TODO Check method definition
        sources, total = await self._source_repo.get_by_domain(domain_id=domain_id, limit=limit, offset=offset)

        # Filter sources based on user access
        authorized_sources = []
        for source in sources:
            try:
                if await self._check_analysis_access(source.search_id, user_id):
                    authorized_sources.append(source)
            except NotFoundException:
                continue

        return authorized_sources, len(authorized_sources)

    async def search_sources(
        self, query: str, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Source], int]:
        """Search through sources with authorization check."""
        #TODO Check method definition
        sources, total = await self._source_repo.search_sources(query=query, limit=limit, offset=offset)

        # Filter sources based on user access
        authorized_sources = []
        for source in sources:
            try:
                if await self._check_analysis_access(source.search_id, user_id):
                    authorized_sources.append(source)
            except NotFoundException:
                continue

        return authorized_sources, len(authorized_sources)
