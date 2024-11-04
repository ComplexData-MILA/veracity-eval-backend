from typing import List, Optional
import aiohttp
from datetime import UTC, datetime
import logging
from uuid import UUID, uuid4
from app.core.config import settings
from sqlalchemy.exc import IntegrityError

from app.models.database.models import SourceModel
from app.services.interfaces.web_search_service import WebSearchServiceInterface
from app.repositories.implementations.source_repository import SourceRepository
from app.services.domain_service import DomainService
from app.core.utils.url import normalize_domain_name

logger = logging.getLogger(__name__)


class GoogleWebSearchService(WebSearchServiceInterface):
    def __init__(self, domain_service: DomainService, source_repository: SourceRepository):
        self.search_endpoint = "https://customsearch.googleapis.com/customsearch/v1"
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.search_engine_id = settings.GOOGLE_SEARCH_ENGINE_ID
        self.domain_service = domain_service
        self.source_repository = source_repository

    async def search_and_create_sources(
        self, claim_text: str, analysis_id: UUID, num_results: int = 5
    ) -> List[SourceModel]:
        """Search for sources and create or update records."""
        try:
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": claim_text,
                "num": min(num_results, 10),
                "fields": "items(title,link,snippet)",
            }

            sources = []
            async with aiohttp.ClientSession() as session:
                async with session.get(self.search_endpoint, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Search API error: {error_text}")
                        return []

                    data = await response.json()
                    if "items" not in data:
                        logger.warning("No search results found")
                        return []

                    for item in data["items"]:
                        try:
                            domain_name = normalize_domain_name(item["link"])
                            domain, is_new = await self.domain_service.get_or_create_domain(domain_name)

                            if is_new:
                                logger.info(f"Created new domain record for: {domain_name}")

                            existing_source = await self._get_existing_source(item["link"])

                            if existing_source:
                                updated_source = await self._update_source_analysis(
                                    existing_source, analysis_id, domain.credibility_score
                                )
                                sources.append(updated_source)
                                logger.debug(f"Updated existing source for URL: {item['link']}")
                            else:
                                source = await self._create_new_source(
                                    item, analysis_id, domain.id, domain.credibility_score
                                )
                                if source:
                                    sources.append(source)
                                    logger.debug(f"Created new source for URL: {item['link']}")

                        except Exception as e:
                            logger.error(f"Error processing search result: {str(e)}", exc_info=True)
                            continue

            return sources

        except Exception as e:
            logger.error(f"Error performing web search: {str(e)}", exc_info=True)
            return []

    async def _get_existing_source(self, url: str) -> Optional[SourceModel]:
        return await self.source_repository.get_by_url(url)

    async def _update_source_analysis(
        self, source: SourceModel, analysis_id: UUID, credibility_score: float
    ) -> SourceModel:
        source.analysis_id = analysis_id
        source.credibility_score = credibility_score
        source.updated_at = datetime.now(UTC)
        return await self.source_repository.update(source)

    async def _create_new_source(
        self, item: dict, analysis_id: UUID, domain_id: UUID, credibility_score: float
    ) -> Optional[SourceModel]:
        try:
            source = SourceModel(
                id=uuid4(),
                analysis_id=analysis_id,
                url=item["link"],
                title=item["title"],
                snippet=item["snippet"],
                domain_id=domain_id,
                content=None,
                credibility_score=credibility_score,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            return await self.source_repository.create_with_domain(source)
        except IntegrityError:
            logger.warning(f"Race condition creating source for URL: {item['link']}")
            existing = await self._get_existing_source(item["link"])
            if existing:
                return await self._update_source_analysis(existing, analysis_id, credibility_score)
            return None

    def format_sources_for_prompt(self, sources: List[SourceModel]) -> str:
        """Format sources into a string for the LLM prompt."""
        if not sources:
            return "No reliable sources found."

        formatted_sources = []
        for i, source in enumerate(sources, 1):
            source_info = [
                f"Source {i}:",
                f"Title: {source.title}",
                f"URL: {source.url}",
                f"Credibility Score: {source.credibility_score:.2f}",
                f"Excerpt: {source.snippet}",
            ]

            if hasattr(source, "domain") and source.domain and source.domain.description:
                source_info.append(f"Domain Info: {source.domain.description}")
                source_info.append(f"Domain Reliability: {'Reliable' if source.domain.is_reliable else 'Unreliable'}")

            formatted_sources.append("\n".join(source_info))

        return "\n\n".join(formatted_sources)

    def calculate_overall_credibility(self, sources: List[SourceModel]) -> float:
        """Calculate overall credibility score for a set of sources."""
        if not sources:
            return 0.0
        return sum(source.credibility_score for source in sources) / len(sources)
