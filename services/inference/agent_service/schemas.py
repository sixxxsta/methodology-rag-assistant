from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: str = ""
    language: str | None = None


class GenerateResponse(BaseModel):
    response: str


class HealthResponse(BaseModel):
    status: str
    model_name: str
    model_loaded: bool
    use_4bit: bool
    response_language: str
    device: str


class ReadyResponse(BaseModel):
    status: str
    model_loaded: bool
