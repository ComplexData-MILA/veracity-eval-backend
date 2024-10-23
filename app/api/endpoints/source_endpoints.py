from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from uuid import UUID

from app.api.dependencies import get_source_service
from app.services.source_service import SourceService
from app.schemas.source_schema import SourceRead, SourceList
from app.core.exceptions import NotFoundException

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/{source_id}", response_model=SourceRead, summary="Get source by ID")
async def get_source(
    source_id: UUID,
    include_content: bool = Query(False, description="Include full source content in response"),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    source_service: SourceService = Depends(get_source_service),
) -> SourceRead:
    """
    Get detailed information about a specific source.
    """
    try:
        source = await source_service.get_source(source_id=source_id, include_content=include_content)
        return SourceRead.model_validate(source)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/analysis/{analysis_id}", response_model=List[SourceRead], summary="Get analysis sources")
async def get_analysis_sources(
    analysis_id: UUID,
    include_content: bool = Query(False, description="Include full source content in response"),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    source_service: SourceService = Depends(get_source_service),
) -> List[SourceRead]:
    """
    Get all sources used in a specific analysis.
    """
    try:
        sources = await source_service.get_analysis_sources(analysis_id=analysis_id, include_content=include_content)
        return [SourceRead.model_validate(s) for s in sources]
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/domain/{domain_id}", response_model=SourceList, summary="Get domain sources")
async def get_domain_sources(
    domain_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    source_service: SourceService = Depends(get_source_service),
) -> SourceList:
    """
    Get all sources from a specific domain.
    """
    sources, total = await source_service.get_domain_sources(domain_id=domain_id, limit=limit, offset=offset)
    return SourceList(items=[SourceRead.model_validate(s) for s in sources], total=total, limit=limit, offset=offset)
