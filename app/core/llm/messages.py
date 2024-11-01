from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from app.core.llm.protocols import LLMMessage, LLMResponse, LLMResponseChunk


@dataclass
class Message:
    """Concrete implementation of LLMMessage protocol."""

    role: str
    content: str

    def __str__(self) -> str:
        return f"{self.role}: {self.content}"


@dataclass
class Response:
    """Concrete implementation of LLMResponse protocol."""

    text: str
    confidence_score: float
    created_at: datetime
    metadata: Dict[str, Any]


@dataclass
class ResponseChunk:
    """Concrete implementation of LLMResponseChunk protocol."""

    text: str
    is_complete: bool
    metadata: Dict[str, Any]


LLMMessage.register(Message)
LLMResponse.register(Response)
LLMResponseChunk.register(ResponseChunk)
