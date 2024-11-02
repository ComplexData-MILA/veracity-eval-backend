from typing import Generic, TypeVar, Optional, List, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)
DomainType = TypeVar("DomainType")


class BaseRepository(Generic[ModelType, DomainType]):
    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        self._session = session
        self._model_class = model_class

    async def create(self, domain_obj: DomainType) -> DomainType:
        """Create with proper async handling."""
        db_obj = self._to_model(domain_obj)
        self._session.add(db_obj)
        await self._session.commit()
        await self._session.refresh(db_obj)
        return self._to_domain(db_obj)

    async def get(self, id: UUID) -> Optional[DomainType]:
        """Get with proper async handling."""
        query = select(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(query)
        db_obj = result.scalar_one_or_none()
        return self._to_domain(db_obj) if db_obj else None

    async def update(self, domain_obj: DomainType) -> DomainType:
        """Update with proper async handling."""
        db_obj = self._to_model(domain_obj)
        merged_obj = await self._session.merge(db_obj)
        await self._session.commit()
        await self._session.refresh(merged_obj)
        return self._to_domain(merged_obj)

    async def get_all(self) -> List[DomainType]:
        query = select(self._model_class)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]

    async def delete(self, id: UUID) -> bool:
        query = delete(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(query)
        await self._session.commit()
        return result.rowcount > 0

    def _to_model(self, domain_obj: DomainType) -> ModelType:
        """Convert domain object to database model"""
        raise NotImplementedError

    def _to_domain(self, model_obj: ModelType) -> DomainType:
        """Convert database model to domain object"""
        raise NotImplementedError
