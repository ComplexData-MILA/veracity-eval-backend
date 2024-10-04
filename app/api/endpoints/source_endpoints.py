from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.source_schema import SourceCreate, SourceRead
from app.services.source_service import SourceService

router = APIRouter()


@router.post("/", response_model=SourceRead)
async def create_source(source_create: SourceCreate, service: SourceService = Depends()):
    source = service.create_source(source_create)
    return SourceRead.model_validate(source)


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: UUID, service: SourceService = Depends()):
    source = service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceRead.model_validate(source)
