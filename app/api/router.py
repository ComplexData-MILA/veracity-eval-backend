from fastapi import APIRouter
from app.api.endpoints import (
    user_endpoints,
    claim_endpoints,
    analysis_endpoints,
    source_endpoints,
    search_endpoints,
    feedback_endpoints,
    conversation_endpoints,
    message_endpoints,
    domain_endpoints,
    health_endpoints,
    claim_conversation_endpoints,
)

router = APIRouter()

router.include_router(user_endpoints.router, tags=["users"])
router.include_router(claim_endpoints.router, tags=["claims"])
router.include_router(analysis_endpoints.router, tags=["analysis"])
router.include_router(source_endpoints.router, tags=["sources"])
router.include_router(search_endpoints.router, tags=["searches"])
router.include_router(feedback_endpoints.router, tags=["feedback"])
router.include_router(conversation_endpoints.router, tags=["conversations"])
router.include_router(message_endpoints.router, tags=["messages"])
router.include_router(domain_endpoints.router, tags=["domains"])
router.include_router(claim_conversation_endpoints.router, tags=["claim-conversations"])
router.include_router(health_endpoints.router, tags=["health"])
