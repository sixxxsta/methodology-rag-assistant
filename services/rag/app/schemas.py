from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    language: str | None = None


class SourceItem(BaseModel):
    source: str
    score: float
    chunk_index: int
    excerpt: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceItem]


class FeedbackRequest(BaseModel):
    session_id: str = ""
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""
    question: str = ""
    answer: str = ""


class IngestResponse(BaseModel):
    files: int
    chunks: int
    collection: str
    total_points: int


class HealthResponse(BaseModel):
    status: str
    llm_provider_configured: str
    llm_provider_active: str
    qdrant_collection: str
    knowledge_points: int
    embedding_model: str
