from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List
from app.schemas.conversation_schema import ConversationCreate, ConversationRead
from app.schemas.claim_conversation_schema import ClaimConversationCreate, ClaimConversationRead
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.post("/", response_model=ConversationRead)
async def create_conversation(conversation_create: ConversationCreate, service: ConversationService = Depends()):
    conversation = service.create_conversation(conversation_create)
    return ConversationRead.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(conversation_id: UUID, service: ConversationService = Depends()):
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conversation)


@router.post("/{conversation_id}/claim-conversations", response_model=ClaimConversationRead)
async def add_claim_conversation(
    conversation_id: UUID, claim_conversation_create: ClaimConversationCreate, service: ConversationService = Depends()
):
    """Add a claim conversation to an existing conversation"""
    claim_conversation = service.add_claim_conversation(conversation_id, claim_conversation_create)
    if not claim_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ClaimConversationRead.model_validate(claim_conversation)


@router.get("/{conversation_id}/claim-conversations", response_model=List[ClaimConversationRead])
async def get_conversation_claim_conversations(conversation_id: UUID, service: ConversationService = Depends()):
    """Get all claim conversations for a specific conversation"""
    claim_conversations = service.get_claim_conversations(conversation_id)
    return [ClaimConversationRead.model_validate(cc) for cc in claim_conversations]
