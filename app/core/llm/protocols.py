from typing import Protocol, Dict, Any
from datetime import datetime


class LLMMessage(Protocol):
    role: str
    content: str


class LLMResponse(Protocol):
    text: str
    confidence_score: float
    created_at: datetime
    metadata: Dict[str, Any]


class LLMResponseChunk(Protocol):
    text: str
    is_complete: bool
    metadata: Dict[str, Any]
