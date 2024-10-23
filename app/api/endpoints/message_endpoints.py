from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.models.domain.user import User
from app.schemas.message_schema import MessageCreate, MessageRead
from app.services.message_service import MessageService
from app.core.exceptions import NotAuthorizedException

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED, summary="Create a new message")
async def create_message(
    data: MessageCreate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    message_service: MessageService = Depends(),
):
    """Create a new message in a conversation."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    try:
        message = await message_service.create_message(
            conversation_id=data.conversation_id,
            sender_type=data.sender_type,
            content=data.content,
            user_id=user.id,
            claim_id=data.claim_id,
            analysis_id=data.analysis_id,
            claim_conversation_id=data.claim_conversation_id,
        )
        return MessageRead.model_validate(message)
    except NotAuthorizedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/conversation/{conversation_id}", response_model=List[MessageRead], summary="Get conversation messages")
async def get_conversation_messages(
    conversation_id: UUID,
    before: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=100),
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    message_service: MessageService = Depends(),
):
    """Get messages from a conversation with pagination."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    try:
        messages = await message_service.get_conversation_messages(
            conversation_id=conversation_id, user_id=user.id, before=before, limit=limit
        )
        return [MessageRead.model_validate(m) for m in messages]
    except NotAuthorizedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "/claim-conversation/{claim_conversation_id}",
    response_model=List[MessageRead],
    summary="Get claim conversation messages",
)
async def get_claim_conversation_messages(
    claim_conversation_id: UUID,
    before: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=100),
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    message_service: MessageService = Depends(),
):
    """Get messages from a claim conversation with pagination."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    try:
        messages = await message_service.get_claim_conversation_messages(
            claim_conversation_id=claim_conversation_id, user_id=user.id, before=before, limit=limit
        )
        return [MessageRead.model_validate(m) for m in messages]
    except NotAuthorizedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
