from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List
from app.schemas.claim_conversation_schema import ClaimConversationCreate, ClaimConversationRead
from app.services.claim_conversation_service import ClaimConversationService

router = APIRouter()


@router.post("/", response_model=ClaimConversationRead)
async def create_claim_conversation(
    claim_conversation_create: ClaimConversationCreate, service: ClaimConversationService = Depends()
):
    claim_conversation = service.create_claim_conversation(claim_conversation_create)
    return ClaimConversationRead.model_validate(claim_conversation)


@router.get("/{claim_conversation_id}", response_model=ClaimConversationRead)
async def get_claim_conversation(claim_conversation_id: UUID, service: ClaimConversationService = Depends()):
    claim_conversation = service.get_claim_conversation(claim_conversation_id)
    if not claim_conversation:
        raise HTTPException(status_code=404, detail="Claim conversation not found")
    return ClaimConversationRead.model_validate(claim_conversation)


@router.get("/conversation/{conversation_id}", response_model=List[ClaimConversationRead])
async def get_claim_conversations_by_conversation(conversation_id: UUID, service: ClaimConversationService = Depends()):
    claim_conversations = service.get_claim_conversations_by_conversation(conversation_id)
    return [ClaimConversationRead.model_validate(cc) for cc in claim_conversations]
