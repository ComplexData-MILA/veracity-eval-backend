from fastapi import APIRouter, Depends, status, HTTPException, Query
from typing import List
from uuid import UUID
import logging

from app.models.domain.user import User
from app.services.post_service import PostService
from app.schemas.post_schema import PostCreate, PostUpdate, PostVote, PostResponse
from app.api.dependencies import get_post_service, get_current_user
from app.core.exceptions import NotFoundException, NotAuthorizedException

router = APIRouter(prefix="/posts", tags=["Posts"])
logger = logging.getLogger(__name__)

# --- CREATE POST ---
@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    service: PostService = Depends(get_post_service),
):
    """Create a new post in a discussion."""
    try:
        return await service.create_post(
            discussion_id=payload.discussion_id,
            user_id=current_user.id,
            text=payload.text
        )
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error creating post")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- UPDATE POST TEXT ---
@router.put("/{post_id}", response_model=PostResponse)
async def update_post_content(
    post_id: UUID,
    payload: PostUpdate,
    current_user: User = Depends(get_current_user),
    service: PostService = Depends(get_post_service),
):
    """
    Update the text content of a post.
    Only the creator of the post can do this.
    """
    try:
        return await service.update_post_text(
            post_id=post_id,
            user_id=current_user.id,
            new_text=payload.text
        )
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAuthorizedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Error updating post")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- VOTE ON POST ---
@router.put("/{post_id}/vote", response_model=PostResponse)
async def vote_on_post(
    post_id: UUID,
    payload: PostVote,
    current_user: User = Depends(get_current_user),
    service: PostService = Depends(get_post_service),
):
    """
    Increment upvotes or downvotes.
    Payload: {"vote_type": "up"} or {"vote_type": "down"}
    """
    try:
        return await service.vote_post(
            post_id=post_id,
            vote_type=payload.vote_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error voting on post")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- DELETE POST ---
@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PostService = Depends(get_post_service),
):
    """Delete a post (Owner only)."""
    try:
        await service.delete_post(post_id=post_id, user_id=current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAuthorizedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Error deleting post")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- GET POSTS BY DISCUSSION ---
@router.get("/discussion/{discussion_id}", response_model=List[PostResponse])
async def list_posts_for_discussion(
    discussion_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: PostService = Depends(get_post_service),
):
    """List all posts belonging to a specific discussion."""
    posts, _ = await service.list_discussion_posts(
        discussion_id=discussion_id, 
        limit=limit, 
        offset=offset
    )
    return posts