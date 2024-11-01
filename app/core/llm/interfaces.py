from abc import ABC, abstractmethod
from typing import AsyncGenerator, List
from app.core.llm.messages import Message, Response, ResponseChunk


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate_response(self, messages: List[Message], temperature: float = 0.7) -> Response:
        """Generate a complete response"""
        pass

    @abstractmethod
    async def generate_stream(
        self, messages: List[Message], temperature: float = 0.7
    ) -> AsyncGenerator[ResponseChunk, None]:
        """Generate a streaming response"""
        pass
