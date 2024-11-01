import logging
from google.cloud import aiplatform
from google.oauth2 import service_account
from typing import AsyncGenerator, List
from datetime import UTC, datetime

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Response, ResponseChunk
from app.core.llm.protocols import LLMMessage

logger = logging.getLogger(__name__)


class VertexAILlamaProvider(LLMProvider):
    def __init__(self, settings):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            client_options = {"api_endpoint": f"{settings.VERTEX_AI_LOCATION}-aiplatform.googleapis.com"}

            aiplatform.init(
                project=settings.GOOGLE_CLOUD_PROJECT, location=settings.VERTEX_AI_LOCATION, credentials=credentials
            )

            self.client = aiplatform.gapic.PredictionServiceClient(
                credentials=credentials, client_options=client_options
            )

            self.endpoint = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/{settings.VERTEX_AI_LOCATION}/endpoints/{settings.VERTEX_AI_ENDPOINT_ID}"

            logger.info(f"Initialized Vertex AI provider with endpoint: {self.endpoint}")

        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI provider: {str(e)}", exc_info=True)
            raise

    async def generate_response(self, messages: List[LLMMessage], temperature: float = 0.7) -> Response:
        try:
            instance = {
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature,
                "max_output_tokens": 1024,
                "model": "llama3-70b-instruct-maas",
            }

            response = self.client.predict(
                endpoint=self.endpoint, instances=[instance], parameters={"temperature": temperature}
            )

            if not response.predictions:
                raise ValueError("No prediction returned from model")

            prediction = response.predictions[0]
            generated_text = prediction["candidates"][0]["content"]

            return Response(
                text=generated_text,
                confidence_score=prediction.get("candidates", [{}])[0]
                .get("safety_attributes", {})
                .get("scores", [0])[0],
                created_at=datetime.now(UTC),
                metadata={"model": "vertexai-llama"},
            )
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, messages: List[LLMMessage], temperature: float = 0.7
    ) -> AsyncGenerator[ResponseChunk, None]:
        try:
            instance = {
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "model": "llama3-70b-instruct-maas",
            }

            logger.debug(f"Starting stream request to Vertex AI: {instance}")

            response = self.client.predict(endpoint=self.endpoint, instances=[instance])

            for prediction in response.predictions:
                if "content" in prediction:
                    yield ResponseChunk(
                        text=prediction["content"], is_complete=False, metadata={"model": "vertexai-llama"}
                    )

            yield ResponseChunk(text="", is_complete=True, metadata={"model": "vertexai-llama"})

        except Exception as e:
            logger.error(f"Error generating stream: {str(e)}", exc_info=True)
            raise
