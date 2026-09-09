from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.versions import PARSER_VERSION, SCHEMA_VERSION

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    status: str = "error"
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    parser_version: str = PARSER_VERSION
    schema_version: str = SCHEMA_VERSION
    phase: str
    environment: str
    llm_enabled: bool


class ExtractionSource(str, Enum):
    REGEX = "regex"
    DICTIONARY = "dictionary"
    TAXONOMY = "taxonomy"
    RULE = "rule"
    NLP = "nlp"
    ML = "ml"
    OCR = "ocr"
    LLM = "llm"
    LAYOUT = "layout"


class SourceSpan(BaseModel):
    page: int | None = None
    bbox: list[float] | None = None
    excerpt: str | None = Field(
        default=None,
        description="Short snippet for audit; never the full resume",
    )


class ExtractedField(BaseModel, Generic[T]):
    raw: str | None = None
    normalized: T | None = None
    value: T | None = None
    confidence: float | None = None
    source: ExtractionSource | None = None
    span: SourceSpan | None = None
    needs_review: bool = False
