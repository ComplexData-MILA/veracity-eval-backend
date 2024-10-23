from google.cloud import aiplatform
from typing import AsyncGenerator, List
from datetime import datetime
import asyncio

from app.core.llm.interfaces import LLMProvider
from app.core.llm.protocols import LLMMessage, LLMResponse, LLMResponseChunk
from app.core.config import Settings


class VertexAILlamaProvider(LLMProvider):
    def __init__(self, settings: Settings):
        self.client = aiplatform.gapic.PredictionServiceClient(
            client_options={"api_endpoint": f"{settings.VERTEX_AI_LOCATION}-aiplatform.googleapis.com"}
        )
        self.project_id = settings.GOOGLE_CLOUD_PROJECT
        self.location = settings.VERTEX_AI_LOCATION
        self.model_name = settings.LLAMA_MODEL_NAME
        self.endpoint = f"projects/{self.project_id}/locations/{self.location}/endpoints/openapi/chat/completions"

    async def generate_response(self, messages: List[LLMMessage], temperature: float = 0.7) -> LLMResponse:
        instance = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }

        response = self.client.predict(endpoint=self.endpoint, instances=[instance])

        return LLMResponse(
            text=response.predictions[0]["content"],
            confidence_score=response.predictions[0].get("confidence", 0.0),
            created_at=datetime.now(),
            metadata={"model": self.model_name},
        )

    async def generate_stream(
        self, messages: List[LLMMessage], temperature: float = 0.7
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        instance = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }

        response = self.client.predict(endpoint=self.endpoint, instances=[instance])

        for chunk in response.predictions[0]["chunks"]:
            yield LLMResponseChunk(text=chunk["content"], is_complete=False, metadata={"model": self.model_name})
            await asyncio.sleep(0.05)  # Natural typing speed simulation

        yield LLMResponseChunk(text="", is_complete=True, metadata={"model": self.model_name})
