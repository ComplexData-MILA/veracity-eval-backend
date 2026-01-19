import logging
import math
from typing import AsyncGenerator, List
from datetime import datetime, timezone
import openai

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message, Response, ResponseChunk

logger = logging.getLogger(__name__)


class TogetherAIProvider(LLMProvider):
    def __init__(self, settings):
        try:
            self.api_key = settings.TOGETHER_API_KEY
            self.base_url = "https://api.together.xyz/v1"
            self.model_id = "meta-llama/Llama-3.3-70B-Instruct-Turbo"  # e.g., "meta-llama/Llama-3.3-70B-Instruct-Turbo"

            if not self.api_key:
                raise ValueError("TOGETHER_API_KEY is not set in settings")

            logger.info(f"Initializing Together AI provider with model: {self.model_id}")

            # Together AI is fully compatible with the OpenAI SDK
            self.client = openai.OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )

            logger.info("Successfully initialized Together AI provider")

        except Exception as e:
            logger.error(f"Failed to initialize Together AI provider: {str(e)}", exc_info=True)
            raise

    def _calculate_confidence(self, logprobs: List[float] | None) -> float:
        """
        Calculates the average confidence score (0.0 to 1.0) from a list of token logprobs.
        """
        if not logprobs:
            return 0.0

        try:
            # 1. Sum up all the log probabilities (negative numbers)
            sum_logprobs = sum(logprobs)

            # 2. Divide by the number of tokens (Length Normalization)
            avg_logprob = sum_logprobs / len(logprobs)

            # 3. Convert back to probability space (0.0 to 1.0)
            return math.exp(avg_logprob)

        except Exception as e:
            logger.warning(f"Math error calculating confidence: {e}")
            return 0.0

    async def generate_response(self, messages: List[Message], temperature: float = 0.7) -> Response:
        try:
            logger.debug(f"Generating response with temperature {temperature}")

            # Synchronous call (OpenAI Python client is sync by default, can use AsyncOpenAI if needed)
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                # CRITICAL: This enables the confidence data you need
                logprobs=5,
            )

            choice = response.choices[0]

            # 1. Extract Logprob object
            logprobs_obj = getattr(choice, "logprobs", None)

            # 2. Get the Log Probs
            logprobs = getattr(logprobs_obj, "token_logprobs", None)

            confidence = self._calculate_confidence(logprobs)

            return Response(
                text=choice.message.content,
                confidence_score=confidence,
                created_at=datetime.now(timezone.utc),
                metadata={
                    "model": self.model_id,
                    "finish_reason": choice.finish_reason,
                    "usage": response.usage.model_dump() if response.usage else None,
                    # We store the full logprobs in case you want to debug specific tokens later
                    "raw_logprobs": logprobs_obj if logprobs_obj else None,
                },
            )

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, messages: List[Message], temperature: float = 0.7
    ) -> AsyncGenerator[ResponseChunk, None]:
        try:
            logger.debug("Starting stream generation")

            stream = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                stream=True,
                logprobs=1,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content

                    # 1. Extract the Logprobs Object

                    chunk_logprobs = getattr(chunk.choices[0], "logprobs", None)

                    yield ResponseChunk(
                        text=content, is_complete=False, metadata={"model": self.model_id, "logprobs": chunk_logprobs}
                    )

            yield ResponseChunk(text="", is_complete=True, metadata={"model": self.model_id})

        except Exception as e:
            logger.error(f"Error in generate_stream: {str(e)}", exc_info=True)
            raise
