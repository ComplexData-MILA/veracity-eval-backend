from abc import ABC, abstractmethod
from typing import Optional, Tuple
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
    async def get_or_create(self, domain_name: str) -> Tuple[Domain, bool]:
        """Get existing domain or create new one."""
        pass
