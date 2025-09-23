import logging
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator


from app.core.auth.auth0_middleware import Auth0Middleware
from app.core.llm.vertex_ai_llama import VertexAILlamaProvider

# from app.db.session import get_session
from app.models.domain.user import User
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.repositories.implementations.user_repository import UserRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.domain_repository import DomainRepository
from app.repositories.implementations.source_repository import SourceRepository
from app.repositories.implementations.search_repository import SearchRepository
from app.repositories.implementations.feedback_repository import FeedbackRepository
from app.core.config import settings
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.claim_conversation_service import ClaimConversationService
from app.services.implementations.web_search_service import GoogleWebSearchService
from app.services.implementations.serper_web_search_service import SerperWebSearchService
from app.services.interfaces.web_search_service import WebSearchServiceInterface
from app.services.implementations.embedding_generator import EmbeddingGenerator
from app.services.interfaces.embedding_generator import EmbeddingGeneratorInterface
from app.services.user_service import UserService
from app.services.claim_service import ClaimService
from app.services.analysis_service import AnalysisService
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.domain_service import DomainService
from app.services.source_service import SourceService
from app.services.search_service import SearchService
from app.services.feedback_service import FeedbackService
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            if session.in_transaction():
                logger.info("Connection being checked back. Likely a read.")
                await session.rollback()
            await session.close()


async def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


async def get_claim_conversation_repository(session: AsyncSession = Depends(get_db)) -> ClaimConversationRepository:
    return ClaimConversationRepository(session)


async def get_claim_repository(session: AsyncSession = Depends(get_db)) -> ClaimRepository:
    return ClaimRepository(session)


async def get_analysis_repository(session: AsyncSession = Depends(get_db)) -> AnalysisRepository:
    return AnalysisRepository(session)


async def get_message_repository(session: AsyncSession = Depends(get_db)) -> MessageRepository:
    return MessageRepository(session)


async def get_conversation_repository(session: AsyncSession = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(session)


async def get_domain_repository(session: AsyncSession = Depends(get_db)) -> DomainRepository:
    return DomainRepository(session)


async def get_source_repository(session: AsyncSession = Depends(get_db)) -> SourceRepository:
    return SourceRepository(session)


async def get_search_repository(session: AsyncSession = Depends(get_db)) -> SearchRepository:
    return SearchRepository(session)


async def get_feedback_repository(session: AsyncSession = Depends(get_db)) -> FeedbackRepository:
    return FeedbackRepository(session)


async def get_embedding_generator() -> EmbeddingGeneratorInterface:
    return EmbeddingGenerator()


async def get_user_service(user_repository: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(user_repository)


async def get_claim_service(
    claim_repository: ClaimRepository = Depends(get_claim_repository),
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
) -> ClaimService:
    return ClaimService(claim_repository, analysis_repository)


async def get_claim_conversation_service(
    conversation_service: ConversationService = Depends(lambda: get_conversation_service()),
    claim_conversation_repository: ClaimConversationRepository = Depends(get_claim_conversation_repository),
) -> ClaimConversationService:
    return ClaimConversationService(conversation_service, claim_conversation_repository)


async def get_analysis_service(
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    claim_repository: ClaimRepository = Depends(get_claim_repository),
) -> AnalysisService:
    return AnalysisService(analysis_repository, claim_repository)


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
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    search_repository: SearchRepository = Depends(get_search_repository),
    claim_repository: ClaimRepository = Depends(get_claim_repository),
) -> SourceService:
    return SourceService(source_repository, domain_service, analysis_repository, search_repository, claim_repository)


async def get_search_service(
    search_repository: SearchRepository = Depends(get_search_repository),
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    claim_repository: ClaimRepository = Depends(get_claim_repository),
) -> SearchService:
    return SearchService(search_repository, analysis_repository, claim_repository)


async def get_feedback_service(
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
) -> FeedbackService:
    return FeedbackService(feedback_repository, analysis_repository)


async def get_llm_provider():
    try:
        provider = VertexAILlamaProvider(settings)
        return provider
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {str(e)}", exc_info=True)
        raise


async def get_web_search_service(
    domain_service: DomainService = Depends(get_domain_service),
    source_repository: SourceRepository = Depends(get_source_repository),
) -> WebSearchServiceInterface:
    return GoogleWebSearchService(domain_service, source_repository)


async def get_serper_web_search_service(
    domain_service: DomainService = Depends(get_domain_service),
    source_repository: SourceRepository = Depends(get_source_repository),
) -> WebSearchServiceInterface:
    return SerperWebSearchService(domain_service, source_repository)


async def get_orchestrator_service(
    claim_repository: ClaimRepository = Depends(get_claim_repository),
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    claim_conversation_repository: ClaimConversationRepository = Depends(get_claim_conversation_repository),
    message_repository: MessageRepository = Depends(get_message_repository),
    source_repository: SourceRepository = Depends(get_source_repository),
    search_repository: SearchRepository = Depends(get_search_repository),
    web_search_service: WebSearchServiceInterface = Depends(get_web_search_service),
    llm_provider=Depends(get_llm_provider),
) -> AnalysisOrchestrator:
    llm_provider = VertexAILlamaProvider(settings)

    return AnalysisOrchestrator(
        claim_repo=claim_repository,
        analysis_repo=analysis_repository,
        conversation_repo=conversation_repository,
        claim_conversation_repo=claim_conversation_repository,
        message_repo=message_repository,
        source_repo=source_repository,
        search_repo=search_repository,
        web_search_service=web_search_service,
        llm_provider=llm_provider,
    )


async def get_serper_orchestrator_service(
    claim_repository: ClaimRepository = Depends(get_claim_repository),
    analysis_repository: AnalysisRepository = Depends(get_analysis_repository),
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    claim_conversation_repository: ClaimConversationRepository = Depends(get_claim_conversation_repository),
    message_repository: MessageRepository = Depends(get_message_repository),
    source_repository: SourceRepository = Depends(get_source_repository),
    search_repository: SearchRepository = Depends(get_search_repository),
    web_search_service: WebSearchServiceInterface = Depends(get_serper_web_search_service),
    llm_provider=Depends(get_llm_provider),
) -> AnalysisOrchestrator:
    llm_provider = VertexAILlamaProvider(settings)

    return AnalysisOrchestrator(
        claim_repo=claim_repository,
        analysis_repo=analysis_repository,
        conversation_repo=conversation_repository,
        claim_conversation_repo=claim_conversation_repository,
        message_repo=message_repository,
        source_repo=source_repository,
        search_repo=search_repository,
        web_search_service=web_search_service,
        llm_provider=llm_provider,
    )


def get_auth_middleware() -> Auth0Middleware:
    return Auth0Middleware()


async def get_current_user(request: Request, auth_middleware: Auth0Middleware = Depends(get_auth_middleware)) -> User:
    return await auth_middleware.authenticate_request(request)
