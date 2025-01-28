import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from uuid import UUID

from app.api.dependencies import get_source_service, get_current_user, get_search_service, get_analysis_service
from app.models.domain.user import User
from app.services.source_service import SourceService
from app.services.search_service import SearchService
from app.schemas.search_schema import SearchRead, SearchList
from app.core.exceptions import NotFoundException, NotAuthorizedException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/searches", tags=["searches"])


@router.get("/{search_id}", response_model=SearchRead, summary="Get search by ID")
async def get_search(
    search_id: UUID,
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchRead:
    """
    Get detailed information about a specific search.
    Includes authorization check to ensure user has access to the analysis this source belongs to.
    """
    try:
        search = await search_service.get_search(
            search_id=search_id, user_id=current_user.id
        )
        return SearchRead.model_validate(search)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this search")


@router.get("/analysis/{analysis_id}", response_model=List[SearchRead], summary="Get analysis searches")
async def get_analysis_searches(
    analysis_id: UUID,
    # include_content: bool = Query(False, description="Include full source content in response"),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> List[SearchRead]:
    """
    Get all searches used in a specific analysis.
    Verifies that the user has access to the analysis before returning searches.
    """
    # TODO include content does not do anything at the moment, it either needs to be removed or created
    try:
        searches = await search_service.get_analysis_searches(
            analysis_id=analysis_id, user_id=current_user.id
        )

        return [SearchRead.model_validate(s) for s in searches]
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access these searches")
    except Exception as e:
        logger.error(f"Error getting searches: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve searches")


