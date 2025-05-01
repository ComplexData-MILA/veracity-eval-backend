from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from app.models.database.models import SourceModel


class WebSearchServiceInterface(ABC):
    @abstractmethod
    async def search_and_create_sources(
        self, claim_text: str, search_id: UUID, num_results: int = 5, language: str = "english", option: List[int] = []
    ) -> List[SourceModel]:
        pass

    @abstractmethod
    async def _get_existing_source(self, url: str) -> Optional[SourceModel]:
        pass

    @abstractmethod
    async def _update_source_analysis(
        self, source: SourceModel, search_id: UUID, credibility_score: float
    ) -> SourceModel:
        pass

    @abstractmethod
    async def _create_new_source(
        self, item: dict, search_id: UUID, domain_id: UUID, credibility_score: float, metadata: bool
    ) -> Optional[SourceModel]:
        pass

    @abstractmethod
    async def _process_metadata(
        self, metatags 
    ) -> str:
        pass

    @abstractmethod
    def format_sources_for_prompt(self, sources: List[SourceModel], language: str = "english") -> str:
        pass

    @abstractmethod
    def calculate_overall_credibility(self, sources: List[SourceModel]) -> float:
        pass
