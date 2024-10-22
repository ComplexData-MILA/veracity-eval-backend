from fastapi import APIRouter
from app.api.endpoints import (
    user_endpoints,
    claim_endpoints,
    analysis_endpoints,
    source_endpoints,
    feedback_endpoints,
    conversation_endpoints,
    message_endpoints,
    domain_endpoints,
    health_endpoints,
    claim_conversation_endpoints,
)

router = APIRouter()

router.include_router(user_endpoints.router, prefix="/users", tags=["users"])
router.include_router(claim_endpoints.router, prefix="/claims", tags=["claims"])
router.include_router(analysis_endpoints.router, prefix="/analysis", tags=["analysis"])
router.include_router(source_endpoints.router, prefix="/sources", tags=["sources"])
router.include_router(feedback_endpoints.router, prefix="/feedback", tags=["feedback"])
router.include_router(conversation_endpoints.router, prefix="/conversations", tags=["conversations"])
router.include_router(message_endpoints.router, prefix="/messages", tags=["messages"])
router.include_router(domain_endpoints.router, prefix="/domains", tags=["domains"])
router.include_router(claim_conversation_endpoints.router, prefix="/claim-conversations", tags=["claim-conversations"])
router.include_router(health_endpoints.router, tags=["health"])
