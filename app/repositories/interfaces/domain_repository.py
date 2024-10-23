from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from app.models.domain.domain import Domain


class DomainRepositoryInterface(ABC):
    """Interface for domain repository operations."""

    @abstractmethod
    async def create(self, domain: Domain) -> Domain:
        """Create new domain."""
        pass

    @abstractmethod
    async def get(self, domain_id: UUID) -> Optional[Domain]:
        """Get domain by ID."""
        pass

    @abstractmethod
    async def get_by_name(self, domain_name: str) -> Optional[Domain]:
        """Get domain by name."""
        pass

    @abstractmethod
    async def update(self, domain: Domain) -> Domain:
        """Update domain."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        reliability_filter: Optional[bool] = None,
        min_credibility: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Domain], int]:
        """Search domains with filters."""
        pass

    @abstractmethod
    async def get_or_create(self, domain_name: str) -> Tuple[Domain, bool]:
        """Get existing domain or create new one."""
        pass
