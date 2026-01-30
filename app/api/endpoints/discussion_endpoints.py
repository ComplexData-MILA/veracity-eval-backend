from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Optional
from uuid import UUID
import logging

from app.models.domain.user import User
from app.services.discussion_service import DiscussionService
from app.schemas.discussion_schema import DiscussionResponse, PaginatedDiscussionsResponse
from app.api.dependencies import get_discussion_service, get_current_user
# 'get_current_user_optional' is useful if you want to know WHO is asking, 
# but allow anonymous users to read discussions.

router = APIRouter(prefix="/discussions", tags=["Discussions"])
logger = logging.getLogger(__name__)

@router.get("/user", response_model=PaginatedDiscussionsResponse)
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
    if current_user.user_id:
        discussions, total = await service.list_user_discussions(current_user.user_id, limit=limit, offset=offset)


    return {
        "items": discussions,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/", response_model=PaginatedDiscussionsResponse)
async def get_recent_discussions(
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

    discussions, total = await service.list_recent_discussions(limit=limit, offset=offset)


    return {
        "items": discussions,
        "total": total,
        "limit": limit,
        "offset": offset
    }

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
        raise HTTPException(status_code=404, detail="Discussion not found")