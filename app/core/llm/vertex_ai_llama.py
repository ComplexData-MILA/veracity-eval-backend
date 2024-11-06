import asyncio
import base64
import json
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
            creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
            logger.info(f"Loading service account from: {creds_path}")

            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Service account file not found at: {creds_path}")

            try:
                with open(creds_path, "r") as f:
                    creds_content = json.loads(f.read())
                    logger.info(f"Using service account: {creds_content.get('client_email')}")
                    logger.info(f"Project ID from creds: {creds_content.get('project_id')}")
                logger.info("Successfully loaded service account as JSON")
            except json.JSONDecodeError:
                logger.info("File is not JSON, attempting base64 decode")
                with open(creds_path, "r") as f:
                    base64_content = f.read()
                    try:
                        decoded_content = base64.b64decode(base64_content)
                        creds_content = json.loads(decoded_content)
                        logger.info(f"Using service account (after base64): {creds_content.get('client_email')}")
                        logger.info(f"Project ID from creds (after base64): {creds_content.get('project_id')}")
                        with open(creds_path, "w") as f:
                            json.dump(creds_content, f)

                        logger.info("Successfully decoded base64 content to JSON")
                    except Exception as e:
                        logger.error(f"Failed to decode base64 content: {str(e)}")
                        raise

            self.credentials = service_account.Credentials.from_service_account_file(
                creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            auth_req = requests.Request()
            self.credentials.refresh(auth_req)

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

            self.model_id = settings.LLAMA_MODEL_NAME
            self.safety_settings = {
                "enabled": True,
                "llama_guard_settings": {},
            }

            logger.info("Successfully initialized Vertex AI Llama provider")
            logger.info(f"Model: {self.model_id}")
            logger.info(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")
            logger.info(f"Location: {settings.VERTEX_AI_LOCATION}")

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
        """Generate a streaming response."""
        try:
            self._refresh_token_if_needed()

            logger.debug("Starting stream generation")
            logger.debug(f"Messages: {messages}")

            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                stream=True,
                extra_body={"extra_body": {"google": {"model_safety_settings": self.safety_settings}}},
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    logger.debug(f"Streaming chunk: {content}")
                    yield ResponseChunk(text=content, is_complete=False, metadata={"model": self.model_id})
                    # Small delay for chunking
                    await asyncio.sleep(0.01)

            yield ResponseChunk(text="", is_complete=True, metadata={"model": self.model_id})

        except Exception as e:
            logger.error(f"Error in generate_stream: {str(e)}", exc_info=True)
            raise
