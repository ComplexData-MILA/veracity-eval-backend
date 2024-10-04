from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List
from app.schemas.message_schema import MessageCreate, MessageRead
from app.services.message_service import MessageService

router = APIRouter()


@router.post("/", response_model=MessageRead)
async def create_message(message_create: MessageCreate, service: MessageService = Depends()):
    message = service.create_message(message_create)
    return MessageRead.model_validate(message)


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(message_id: UUID, service: MessageService = Depends()):
    message = service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageRead.model_validate(message)


@router.get("/conversation/{conversation_id}", response_model=List[MessageRead])
async def get_messages_by_conversation(conversation_id: UUID, service: MessageService = Depends()):
    messages = service.get_messages_by_conversation(conversation_id)
    return [MessageRead.model_validate(message) for message in messages]
