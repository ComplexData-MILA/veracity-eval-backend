from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.repositories.implementations.user_repository import UserRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.domain_repository import DomainRepository
from app.repositories.implementations.source_repository import SourceRepository
from app.repositories.implementations.feedback_repository import FeedbackRepository

from app.services.claim_conversation_service import ClaimConversationService
from app.services.user_service import UserService
from app.services.claim_service import ClaimService
from app.services.analysis_service import AnalysisService
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.domain_service import DomainService
from app.services.source_service import SourceService
from app.services.feedback_service import FeedbackService


# Database Session Dependency
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        Session: The database session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Repository Dependencies
async def get_user_repository(session: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


async def get_claim_conversation_repository(session: Session = Depends(get_db)) -> ClaimConversationRepository:
    return ClaimConversationRepository(session)


async def get_claim_repository(session: Session = Depends(get_db)) -> ClaimRepository:
    return ClaimRepository(session)


async def get_analysis_repository(session: Session = Depends(get_db)) -> AnalysisRepository:
    return AnalysisRepository(session)


async def get_message_repository(session: Session = Depends(get_db)) -> MessageRepository:
    return MessageRepository(session)


async def get_conversation_repository(session: Session = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(session)


async def get_domain_repository(session: Session = Depends(get_db)) -> DomainRepository:
    return DomainRepository(session)


async def get_source_repository(session: Session = Depends(get_db)) -> SourceRepository:
    return SourceRepository(session)


async def get_feedback_repository(session: Session = Depends(get_db)) -> FeedbackRepository:
    return FeedbackRepository(session)


# Service Dependencies
async def get_user_service(user_repository: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repository)


async def get_claim_service(
    claim_repository: ClaimRepository = Depends(get_claim_repository),
    analysis_service: AnalysisService = Depends(lambda: get_analysis_service()),
) -> ClaimService:
    return ClaimService(claim_repository, analysis_service)


async def get_claim_conversation_service(
    conversation_service: ConversationService = Depends(lambda: get_conversation_service()),
    claim_conversation_repository: ClaimConversationRepository = Depends(get_claim_conversation_repository),
) -> ClaimConversationService:
    return ClaimConversationService(conversation_service, claim_conversation_repository)


async def get_analysis_service(
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    source_service: SourceService = Depends(lambda: get_source_service()),
) -> AnalysisService:
    return AnalysisService(analysis_repository, source_service)


async def get_message_service(
    message_repository: MessageRepository = Depends(get_message_repository),
    conversation_service: ConversationService = Depends(lambda: get_conversation_service()),
) -> MessageService:
    return MessageService(message_repository, conversation_service)


async def get_conversation_service(
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    claim_conversation_repository: ClaimConversationRepository = Depends(get_claim_conversation_repository),
) -> ConversationService:
    return ConversationService(conversation_repository, claim_conversation_repository)


async def get_domain_service(domain_repository: DomainRepository = Depends(get_domain_repository)) -> DomainService:
    return DomainService(domain_repository)


async def get_source_service(
    source_repository: SourceRepository = Depends(get_source_repository),
    domain_service: DomainService = Depends(get_domain_service),
) -> SourceService:
    return SourceService(source_repository, domain_service)


async def get_feedback_service(
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
) -> FeedbackService:
    return FeedbackService(feedback_repository)
