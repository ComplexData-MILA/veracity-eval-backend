from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from uuid import UUID

from app.models.database.conversation import ConversationStatus
from app.models.domain.user import User
from app.services.conversation_service import ConversationService
from app.schemas.conversation_schema import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationList,
)
from app.core.exceptions import NotFoundException, NotAuthorizedException

# from app.api.dependencies import get_current_user_and_session

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED, summary="Create a new conversation"
)
async def create_conversation(
    data: ConversationCreate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    conversation_service: ConversationService = Depends(),
):
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    conversation = await conversation_service.create_conversation(user_id=user.id)
    return ConversationRead.model_validate(conversation)


@router.get("/", response_model=ConversationList, summary="List user conversations")
async def list_conversations(
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    conversation_service: ConversationService = Depends(),
):
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    conversations, total = await conversation_service.list_user_conversations(
        user_id=user.id, status=status, limit=limit, offset=offset
    )
    return ConversationList(
        items=[ConversationRead.model_validate(c) for c in conversations], total=total, limit=limit, offset=offset
    )


@router.get("/{conversation_id}", response_model=ConversationRead, summary="Get conversation by ID")
async def get_conversation(
    conversation_id: UUID,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    conversation_service: ConversationService = Depends(),
):
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    try:
        conversation = await conversation_service.get_conversation(conversation_id=conversation_id, user_id=user.id)
        return ConversationRead.model_validate(conversation)
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{conversation_id}", response_model=ConversationRead, summary="Update conversation status")
async def update_conversation(
    conversation_id: UUID,
    data: ConversationUpdate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    conversation_service: ConversationService = Depends(),
):
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")
    try:
        conversation = await conversation_service.update_conversation_status(
            conversation_id=conversation_id, user_id=user.id, status=ConversationStatus(data.status)
        )
        return ConversationRead.model_validate(conversation)
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
