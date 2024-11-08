from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID

from app.api.dependencies import get_claim_conversation_service, get_current_user
from app.models.domain.user import User
from app.services.claim_conversation_service import ClaimConversationService
from app.schemas.claim_conversation_schema import (
    ClaimConversationCreate,
    ClaimConversationRead,
)
from app.core.exceptions import NotFoundException, NotAuthorizedException

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/{conversation_id}/claims",
    response_model=ClaimConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_claim_conversation(
    conversation_id: UUID,
    data: ClaimConversationCreate,
    current_user: User = Depends(get_current_user),
    claim_conversation_service: ClaimConversationService = Depends(get_claim_conversation_service),
):
    """Create a new claim conversation."""
    try:
        claim_conv, _ = await claim_conversation_service.create_claim_conversation(
            conversation_id=conversation_id, user_id=current_user.id, claim_id=data.claim_id
        )
        return ClaimConversationRead.model_validate(claim_conv)
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{conversation_id}/claims", response_model=List[ClaimConversationRead])
async def list_claim_conversations(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    claim_conversation_service: ClaimConversationService = Depends(get_claim_conversation_service),
):
    """List all claim conversations for a conversation."""
    try:
        claim_convs = await claim_conversation_service.list_conversation_claims(
            conversation_id=conversation_id, user_id=current_user.id
        )
        return [ClaimConversationRead.model_validate(cc) for cc in claim_convs]
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
