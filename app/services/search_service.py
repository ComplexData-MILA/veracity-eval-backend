import logging
from typing import List, Tuple
from uuid import UUID

from app.models.domain.search import Search
from app.repositories.implementations.search_repository import SearchRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        search_repository: SearchRepository,
        analysis_repository: AnalysisRepository,
        claim_repository: ClaimRepository,
    ):
        self._search_repo = search_repository
        self._analysis_repo = analysis_repository
        self._claim_repo = claim_repository

    async def _check_analysis_access(self, analysis_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to the analysis."""
        analysis = await self._analysis_repo.get(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis not found")

        claim = await self._claim_repo.get(analysis.claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        # User has access if they own the claim
        return claim.user_id == user_id

    async def get_search(self, search_id: UUID, user_id: UUID) -> Search:
        """Get source by ID with authorization check."""
        search = await self._search_repo.get(search_id)
        if not search:
            raise NotFoundException("Search not found")

        if not await self._check_analysis_access(search.analysis_id, user_id):
            raise NotAuthorizedException("Not authorized to access this source")

        return search

    async def get_analysis_searches(
        self, analysis_id: UUID, user_id: UUID
    ) -> List[Search]:
        """Get all searches for an analysis with authorization check."""
        logger.debug(f"Getting searches for analysis {analysis_id} for user {user_id}")

        if not await self._check_analysis_access(analysis_id, user_id):
            logger.warning(f"User {user_id} not authorized to access analysis {analysis_id}")
            raise NotAuthorizedException("Not authorized to access these searches")

        try:
            searches = await self._search_repo.get_by_analysis(
                analysis_id=analysis_id,
            )
            logger.debug(f"Found {len(searches)} searches for analysis {analysis_id}")
            return searches
        except Exception as e:
            logger.error(f"Error getting searches for analysis {analysis_id}: {str(e)}")
            raise
