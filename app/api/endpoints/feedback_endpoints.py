from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.feedback_schema import FeedbackCreate, FeedbackRead
from app.services.feedback_service import FeedbackService

router = APIRouter()


@router.post("/", response_model=FeedbackRead)
async def create_feedback(feedback_create: FeedbackCreate, service: FeedbackService = Depends()):
    feedback = service.create_feedback(feedback_create)
    return FeedbackRead.model_validate(feedback)


@router.get("/{feedback_id}", response_model=FeedbackRead)
async def get_feedback(feedback_id: UUID, service: FeedbackService = Depends()):
    feedback = service.get_feedback(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return FeedbackRead.model_validate(feedback)
