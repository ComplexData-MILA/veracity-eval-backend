from abc import ABC, abstractmethod
from typing import AsyncGenerator, List
from app.core.llm.protocols import LLMMessage, LLMResponse, LLMResponseChunk


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate_response(self, messages: List[LLMMessage], temperature: float = 0.7) -> LLMResponse:
        """Generate a complete response"""
        pass

    @abstractmethod
    async def generate_stream(
        self, messages: List[LLMMessage], temperature: float = 0.7
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """Generate a streaming response"""
        pass
