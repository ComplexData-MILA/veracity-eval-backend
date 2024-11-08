import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from datetime import UTC, datetime

from fastapi.responses import StreamingResponse

from app.api.dependencies import get_message_service, get_orchestrator_service
from app.models.domain.user import User
from app.schemas.message_schema import MessageCreate, MessageRead
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.message_service import MessageService
from app.core.exceptions import NotAuthorizedException

router = APIRouter(prefix="/messages", tags=["messages"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED, summary="Create a new message")
async def create_message(
    data: MessageCreate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    message_service: MessageService = Depends(get_message_service),
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
    message_service: MessageService = Depends(get_message_service),
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
    message_service: MessageService = Depends(get_message_service),
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


@router.get("/stream", response_class=StreamingResponse)
async def stream_message(
    conversation_id: UUID,
    claim_conversation_id: UUID,
    claim_id: UUID,
    content: str,
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator_service),
) -> StreamingResponse:
    """Stream an interactive response in a claim conversation."""
    # fake user for now
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        email="bob@test.com",
        auth0_id="auth0|1234567890",
        username="bob",
        is_active=True,
        last_login=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def event_generator():
        try:
            async for event in orchestrator.stream_claim_discussion(
                conversation_id=conversation_id,
                claim_conversation_id=claim_conversation_id,
                claim_id=claim_id,
                user_id=user.id,
                message_content=content,
            ):
                # Ensure each chunk is flushed immediately
                chunk = f"data: {json.dumps(event)}\n\n"
                yield chunk.encode("utf-8")
                await asyncio.sleep(0)  # Allow other tasks to run

        except Exception as e:
            logger.error(f"Error in message stream: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n".encode("utf-8")
        finally:
            yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )
