import logging
import os
from typing import AsyncGenerator, List
from datetime import UTC, datetime
import openai
from google.oauth2 import service_account
from google.auth.transport import requests

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message, Response, ResponseChunk

logger = logging.getLogger(__name__)


class VertexAILlamaProvider(LLMProvider):
    def __init__(self, settings):
        try:
            logger.info(f"Loading service account from: {settings.GOOGLE_APPLICATION_CREDENTIALS}")

            if not os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                raise FileNotFoundError(f"Service account file not found at: {settings.GOOGLE_APPLICATION_CREDENTIALS}")

            # Initialize credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Get initial access token
            auth_req = requests.Request()
            self.credentials.refresh(auth_req)

            # Configure base URL correctly for OpenAI client
            project_path = f"projects/{settings.GOOGLE_CLOUD_PROJECT}"
            location_path = f"locations/{settings.VERTEX_AI_LOCATION}"
            base_url = (
                f"https://{settings.VERTEX_AI_LOCATION}-aiplatform.googleapis.com/v1/"
                f"{project_path}/{location_path}/endpoints/openapi"
            )

            logger.info(f"Initializing OpenAI client with base URL: {base_url}")

            self.client = openai.OpenAI(
                base_url=base_url,
                api_key=self.credentials.token,
                default_headers={"Authorization": f"Bearer {self.credentials.token}"},
            )

            # Store configuration
            self.model_id = settings.LLAMA_MODEL_NAME
            self.safety_settings = {
                "enabled": True,
                "llama_guard_settings": {},
            }

            logger.info("Successfully initialized Vertex AI Llama provider")
            logger.info(f"Model: {self.model_id}")
            logger.info(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")
            logger.info(f"Location: {settings.VERTEX_AI_LOCATION}")

        except FileNotFoundError as e:
            logger.error(f"Service account file error: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI Llama provider: {str(e)}", exc_info=True)
            raise

    def _refresh_token_if_needed(self):
        """Refresh the access token if needed"""
        if not self.credentials.valid:
            auth_req = requests.Request()
            self.credentials.refresh(auth_req)
            # Update client with new token
            self.client.api_key = self.credentials.token
            self.client.default_headers["Authorization"] = f"Bearer {self.credentials.token}"
            logger.info("Refreshed access token")

    async def generate_response(self, messages: List[Message], temperature: float = 0.7) -> Response:
        try:
            self._refresh_token_if_needed()

            logger.debug(f"Generating response with temperature {temperature}")
            logger.debug(f"Number of messages: {len(messages)}")
            logger.debug(f"Model ID: {self.model_id}")

            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                extra_body={"extra_body": {"google": {"model_safety_settings": self.safety_settings}}},
            )

            return Response(
                text=response.choices[0].message.content,
                confidence_score=response.choices[0].finish_reason != "content_filtered",
                created_at=datetime.now(UTC),
                metadata={"model": self.model_id, "finish_reason": response.choices[0].finish_reason},
            )

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            if hasattr(e, "response"):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise

    async def generate_stream(
        self, messages: List[Message], temperature: float = 0.7
    ) -> AsyncGenerator[ResponseChunk, None]:
        try:
            self._refresh_token_if_needed()

            logger.debug(f"Starting stream generation with temperature {temperature}")
            logger.debug(f"Number of messages: {len(messages)}")

            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                stream=True,
                extra_body={"extra_body": {"google": {"model_safety_settings": self.safety_settings}}},
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield ResponseChunk(
                        text=chunk.choices[0].delta.content, is_complete=False, metadata={"model": self.model_id}
                    )

            yield ResponseChunk(text="", is_complete=True, metadata={"model": self.model_id})

        except Exception as e:
            logger.error(f"Error generating stream: {str(e)}", exc_info=True)
            if hasattr(e, "response"):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise
