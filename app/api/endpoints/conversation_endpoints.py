from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_conversation_service, get_current_user
from app.models.database.models import ConversationStatus
from app.models.domain.user import User
from app.services.conversation_service import ConversationService
from app.schemas.conversation_schema import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationList,
)
from app.core.exceptions import NotFoundException, NotAuthorizedException

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED, summary="Create a new conversation"
)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationRead:
    """
    Create a new conversation for the authenticated user.
    """
    try:
        conversation = await conversation_service.create_conversation(user_id=current_user.id)
        return ConversationRead.model_validate(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create conversation: {str(e)}"
        )


@router.get("/", response_model=ConversationList, summary="List user conversations")
async def list_conversations(
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationList:
    """
    List all conversations for the authenticated user with pagination.
    """
    try:
        conversations, total = await conversation_service.list_user_conversations(
            user_id=current_user.id, status=status, limit=limit, offset=offset
        )
        return ConversationList(
            items=[ConversationRead.model_validate(c) for c in conversations], total=total, limit=limit, offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list conversations: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=ConversationRead, summary="Get conversation by ID")
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationRead:
    """
    Get a specific conversation by ID. User must own the conversation.
    """
    try:
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id, user_id=current_user.id
        )
        return ConversationRead.model_validate(conversation)
    except NotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this conversation")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get conversation: {str(e)}"
        )


@router.patch("/{conversation_id}", response_model=ConversationRead, summary="Update conversation status")
async def update_conversation(
    conversation_id: UUID,
    data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationRead:
    """
    Update a conversation's status. User must own the conversation.
    """
    try:
        # First verify ownership
        await conversation_service.get_conversation(conversation_id, current_user.id)

        conversation = await conversation_service.update_status(
            conversation_id=conversation_id, user_id=current_user.id, status=ConversationStatus(data.status)
        )
        return ConversationRead.model_validate(conversation)
    except NotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this conversation")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status value: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update conversation: {str(e)}"
        )


@router.post("/{conversation_id}/end", response_model=ConversationRead, summary="End a conversation")
async def end_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationRead:
    """
    End a conversation. This will mark it as completed and set the end time.
    User must own the conversation.
    """
    try:
        # First verify ownership
        await conversation_service.get_conversation(conversation_id, current_user.id)

        conversation = await conversation_service.end_conversation(conversation_id=conversation_id)
        return ConversationRead.model_validate(conversation)
    except NotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to end this conversation")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to end conversation: {str(e)}"
        )


@router.get("/active", response_model=Optional[ConversationRead], summary="Get user's active conversation")
async def get_active_conversation(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> Optional[ConversationRead]:
    """
    Get the user's current active conversation, if any exists.
    """
    try:
        conversation = await conversation_service.get_active_conversation(user_id=current_user.id)
        if not conversation:
            return None
        return ConversationRead.model_validate(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get active conversation: {str(e)}"
        )
