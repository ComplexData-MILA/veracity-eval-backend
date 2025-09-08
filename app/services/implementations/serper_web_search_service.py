from typing import List, Optional
import aiohttp
from datetime import UTC, datetime
import logging
from uuid import UUID, uuid4
from app.core.config import settings
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ValidationError
from app.models.database.models import SourceModel
from app.services.interfaces.web_search_service import WebSearchServiceInterface
from app.repositories.implementations.source_repository import SourceRepository
from app.services.domain_service import DomainService
from app.core.utils.url import normalize_domain_name

logger = logging.getLogger(__name__)


class SerperWebSearchService(WebSearchServiceInterface):
    def __init__(self, domain_service: DomainService, source_repository: SourceRepository):
        self.search_endpoint = "https://google.serper.dev/search"
        self.api_key = settings.SERPER_API_KEY
        self.domain_service = domain_service
        self.source_repository = source_repository

    async def search_and_create_sources(
        self, claim_text: str, search_id: UUID, num_results: int = 5, language: str = "english"
    ) -> List[SourceModel]:
        """Search for sources and create or update records."""
        try:
            payload = {
                "q": claim_text,
                "location": "Canada",
                "gl": "ca"
            }
            # if language == "english":
            #     params = {
            #         "key": self.api_key,
            #         "cx": self.search_engine_id,
            #         "q": claim_text,
            #         "num": min(num_results, 10),
            #         "fields": "items(title,link,snippet)",
            #         "lr": "lang_en",
            #     }
            if language == "french":
                payload = {  
                    "q": "apple inc",
                    "location": "Canada",
                    "gl": "ca",
                    "hl": "fr"
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

                            source = await self._create_new_source(item, search_id, domain.id, domain.credibility_score)
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
        self, source: SourceModel, search_id: UUID, credibility_score: float
    ) -> SourceModel:
        source.search_id = search_id
        source.credibility_score = credibility_score
        source.updated_at = datetime.now(UTC)
        return await self.source_repository.update(source)

    async def _create_new_source(
        self, item: dict, search_id: UUID, domain_id: UUID, credibility_score: float
    ) -> Optional[SourceModel]:
        try:
            source = SourceModel(
                id=uuid4(),
                search_id=search_id,
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
                return await self._update_source_analysis(existing, search_id, credibility_score)
            return None

    def format_sources_for_prompt(self, sources: List[SourceModel], language: str = "english") -> str:
        """Format sources into a string for the LLM prompt."""
        if language == "english":
            if not sources:
                return "No reliable sources found."

            formatted_sources = []
            for i, source in enumerate(sources, 1):
                source_info = [
                    f"Source {i}:",
                    f"Title: {source.title}",
                    f"URL: {source.url}",
                    f"Credibility Score: {source.credibility_score:.2f}"
                    if source.credibility_score is not None
                    else "Credibility Score: N/A",
                    f"Excerpt: {source.snippet}",
                ]

                if hasattr(source, "domain") and source.domain and source.domain.description:
                    source_info.append(f"Domain Info: {source.domain.description}")

                formatted_sources.append("\n".join(source_info))

            return "\n\n".join(formatted_sources)

        elif language == "french":
            if not sources:
                return "Il n'y a pas des sources."

            formatted_sources = []
            for i, source in enumerate(sources, 1):
                source_info = [
                    f"Source {i}:",
                    f"Titre: {source.title}",
                    f"URL: {source.url}",
                    f"Index de crédibilité: {source.credibility_score:.2f}"
                    if source.credibility_score is not None
                    else "Index de crédibilité: N/A",
                    f"Extrait: {source.snippet}",
                ]

                if hasattr(source, "domain") and source.domain and source.domain.description:
                    source_info.append(f"Informations sur le domaine: {source.domain.description}")

                formatted_sources.append("\n".join(source_info))

            return "\n\n".join(formatted_sources)
        else:
            raise ValidationError("Claim Language is invalid")

    def calculate_overall_credibility(self, sources: List[SourceModel]) -> float:
        """Calculate overall credibility score for a set of sources."""
        if not sources:
            return 0.0

        # Filter out sources with null credibility scores
        valid_scores = [source.credibility_score for source in sources if source.credibility_score is not None]

        if not valid_scores:
            return 0.0  # Return 0.0 if no valid scores exist

        # Calculate the average of the valid scores
        return sum(valid_scores) / len(valid_scores)
