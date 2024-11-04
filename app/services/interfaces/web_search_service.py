from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from app.models.database.models import SourceModel


class WebSearchServiceInterface(ABC):
    @abstractmethod
    async def search_and_create_sources(
        self, claim_text: str, analysis_id: UUID, num_results: int = 5
    ) -> List[SourceModel]:
        pass

    @abstractmethod
    async def _get_existing_source(self, url: str) -> Optional[SourceModel]:
        pass

    @abstractmethod
    async def _update_source_analysis(
        self, source: SourceModel, analysis_id: UUID, credibility_score: float
    ) -> SourceModel:
        pass

    @abstractmethod
    async def _create_new_source(
        self, item: dict, analysis_id: UUID, domain_id: UUID, credibility_score: float
    ) -> Optional[SourceModel]:
        pass

    @abstractmethod
    def format_sources_for_prompt(self, sources: List[SourceModel]) -> str:
        pass

    @abstractmethod
    def calculate_overall_credibility(self, sources: List[SourceModel]) -> float:
        pass
