"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field, model_validator
from enum import Enum
from typing import Optional, List


class ContentType(str, Enum):
    """Supported knowledge base source types for upload."""
    text = "text"
    website = "website"
    pdf_url = "pdf_url"
    pdf_base64 = "pdf_base64"
    pdf_file = "pdf_file"


class UploadRequest(BaseModel):
    """Request model for knowledge base upload."""
    content_type: ContentType
    text_content: Optional[str] = Field(default=None, min_length=1, description="Plain text knowledge base content")
    website_url: Optional[str] = Field(default=None, min_length=1, description="Public webpage URL to ingest")
    pdf_url: Optional[str] = Field(default=None, min_length=1, description="Direct URL to a PDF file")
    pdf_base64_content: Optional[str] = Field(default=None, min_length=1, description="Base64-encoded PDF content")
    metadata: Optional[dict] = Field(default_factory=dict, description="Optional metadata for the knowledge base")

    @model_validator(mode="after")
    def validate_source_payload(self):
        source_fields = {
            ContentType.text: self.text_content,
            ContentType.website: self.website_url,
            ContentType.pdf_url: self.pdf_url,
            ContentType.pdf_base64: self.pdf_base64_content,
        }
        selected_value = source_fields.get(self.content_type)
        if not selected_value:
            raise ValueError(f"{self.content_type.value} requires its matching field to be provided")
        return self

class UploadResponse(BaseModel):
    """Response model for successful upload."""
    bot_id: str
    chunks_created: int
    tokens_ingested: int
    source_type: str
    message: str


class ChatMessage(BaseModel):
    """Individual message in conversation history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    bot_id: str
    user_message: str = Field(..., min_length=1)
    conversation_history: Optional[List[ChatMessage]] = Field(default_factory=list)


class ChatDeltaResponse(BaseModel):
    """Streaming response delta."""
    delta: str
    finish_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    grounded: Optional[bool] = None
    error: Optional[str] = None


class StatsResponse(BaseModel):
    """Response model for bot statistics."""
    bot_id: str
    total_messages_served: int
    average_response_latency_ms: float
    estimated_token_cost_usd: float
    unanswered_questions: int
    answerable_rate_pct: float
    created_at: str
    last_active_at: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    api: str
    qdrant: str
    litellm_proxy: str
    sqlite: str
