from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional

ExtractionReason = Literal["ok", "no_claims", "llm_error", "too_long"]

SUPPORTED_LANGUAGES = ("english", "french")


class ClaimExtractionRequest(BaseModel):
    """Schema for extracting verifiable statements from free text."""

    text: str = Field(..., min_length=1, max_length=60_000)
    language: str = "english"

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError(f"language must be one of {SUPPORTED_LANGUAGES}")
        return value


class ExtractedStatement(BaseModel):
    """A single self-contained statement that can be fact-checked."""

    id: str
    text: str


class ClaimExtractionResponse(BaseModel):
    """Schema for the outcome of a claim extraction request."""

    statements: List[ExtractedStatement]
    reason: ExtractionReason = "ok"
    language: str


class ClarificationTurn(BaseModel):
    """A clarifying question already shown to the user, and their answer (null if skipped)."""

    question: str = Field(..., min_length=1, max_length=1000)
    answer: Optional[str] = Field(None, max_length=1000)


class ClaimClarificationRequest(ClaimExtractionRequest):
    """Schema for deciding whether a claim needs clarifying before it is fact-checked."""

    text: str = Field(..., min_length=1, max_length=2000)
    turns: List[ClarificationTurn] = Field(default_factory=list, max_length=5)


class ClaimClarificationResponse(BaseModel):
    """Either a question to show the user, or the clarified claim to submit to POST /claims/."""

    status: Literal["ask", "ready"]
    claim: str
    question: Optional[str] = None
    options: List[str] = []
    assumptions: List[str] = []
    language: str
