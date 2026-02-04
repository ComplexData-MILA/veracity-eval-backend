from fastapi import APIRouter, Depends, Query, status, HTTPException

# from typing import Optional
from uuid import UUID
import logging

from app.models.domain.user import User
from app.services.discussion_service import DiscussionService
from app.schemas.discussion_schema import DiscussionResponse, PaginatedDiscussionsResponse, DiscussionCreate
from app.api.dependencies import get_discussion_service, get_current_user

# 'get_current_user_optional' is useful if you want to know WHO is asking,
# but allow anonymous users to read discussions.

router = APIRouter(prefix="/discussions", tags=["discussions"])
logger = logging.getLogger(__name__)


@router.get("/user", response_model=PaginatedDiscussionsResponse, status_code=status.HTTP_200_OK)
async def get_discussions_per_user(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: DiscussionService = Depends(get_discussion_service),
):
    """
    Get a list of discussions.
    - If `user_id` is provided, returns discussions for that user.
    - Otherwise, returns the most recent discussions system-wide.
    """
    if current_user.id:
        discussions, total = await service.list_user_discussions(current_user.id, limit=limit, offset=offset)

    return {"items": discussions, "total": total, "limit": limit, "offset": offset}


@router.get("/", response_model=PaginatedDiscussionsResponse, status_code=status.HTTP_200_OK)
async def get_recent_discussions(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: DiscussionService = Depends(get_discussion_service),
):
    """
    Get a list of discussions.
    - If `user_id` is provided, returns discussions for that user.
    - Otherwise, returns the most recent discussions system-wide.
    """

    discussions, total = await service.list_recent_discussions(limit=limit, offset=offset)

    return {"items": discussions, "total": total, "limit": limit, "offset": offset}


@router.get("/{discussion_id}", response_model=DiscussionResponse)
async def get_discussion_by_id(
    discussion_id: UUID,
    service: DiscussionService = Depends(get_discussion_service),
):
    """Get a single discussion by ID."""
    try:
        return await service.get_discussion(discussion_id)
    except Exception as e:
        # Assuming your service raises NotFoundException
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=DiscussionResponse, status_code=status.HTTP_201_CREATED)
async def create_discussion(
    payload: DiscussionCreate,
    current_user: User = Depends(get_current_user),
    service: DiscussionService = Depends(get_discussion_service),
):
    """
    Create a new discussion.
    - Requires authentication.
    - 'analysis_id' is optional (use it if you want to attach the discussion to a specific claim analysis).
    """
    discussion = await service.create_discussion(
        title=payload.title,
        description=payload.description,
        analysis_id=payload.analysis_id,
        user_id=current_user.id,  # Matches your User model field
    )

    return discussion
