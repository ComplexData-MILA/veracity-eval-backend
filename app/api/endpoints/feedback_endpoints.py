from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID

from app.api.dependencies import get_feedback_service, get_current_user
from app.models.domain.user import User
from app.schemas.feedback_schema import FeedbackCreate, FeedbackList, FeedbackRead
from app.services.feedback_service import FeedbackService
from app.core.exceptions import NotFoundException, DuplicateFeedbackError

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    try:
        feedback = await feedback_service.create_feedback(
            user_id=current_user.id,
            analysis_id=data.analysis_id,
            rating=data.rating,
            comment=data.comment,
            labels=data.labels,
        )
        return FeedbackRead.model_validate(feedback)
    except (NotFoundException, DuplicateFeedbackError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analysis/{analysis_id}", response_model=FeedbackList)
async def get_analysis_feedback(
    analysis_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    feedback_list, total = await feedback_service.get_analysis_feedback(
        analysis_id=analysis_id, limit=limit, offset=offset
    )
    return FeedbackList(
        items=[FeedbackRead.model_validate(f) for f in feedback_list], total=total, limit=limit, offset=offset
    )


@router.get("/user", response_model=FeedbackList)
async def get_user_feedback(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    feedback_list, total = await feedback_service.get_user_feedback(user_id=current_user.id, limit=limit, offset=offset)
    return FeedbackList(
        items=[FeedbackRead.model_validate(f) for f in feedback_list], total=total, limit=limit, offset=offset
    )
