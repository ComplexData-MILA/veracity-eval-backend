from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.conversation_schema import ConversationCreate, ConversationRead
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
