from typing import Generic, TypeVar, Optional, List, Type
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)
DomainType = TypeVar("DomainType")


class BaseRepository(Generic[ModelType, DomainType]):
    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        self._session = session
        self._model_class = model_class

    async def get(self, id: UUID) -> Optional[DomainType]:
        query = select(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        self._session.expunge(model)
        return self._to_domain(model)

    async def get_all(self) -> List[DomainType]:
        query = select(self._model_class)
        result = await self._session.execute(query)
        models = result.scalars().all()

        for model in models:
            self._session.expunge(model)

        return [self._to_domain(model) for model in models]

    async def create(self, entity: DomainType) -> DomainType:
        model = self._to_model(entity)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        self._session.expunge(model)
        return self._to_domain(model)

    async def update(self, entity: DomainType) -> Optional[DomainType]:
        model = self._to_model(entity)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        self._session.expunge(model)
        return self._to_domain(model)

    async def delete(self, id: UUID) -> bool:
        model = await self._session.get(self._model_class, id)
        if model:
            await self._session.delete(model)
            await self._session.commit()
            return True
        return False

    def _to_model(self, entity: DomainType) -> ModelType:
        raise NotImplementedError

    def _to_domain(self, model: ModelType) -> DomainType:
        raise NotImplementedError
