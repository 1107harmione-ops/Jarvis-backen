from typing import Optional

from pydantic import BaseModel, Field


class STTRequest(BaseModel):
    audio: str = Field(..., description="Base64-encoded audio data")
    format: str = "wav"


class STTResponse(BaseModel):
    text: str
    confidence: float
    provider: str


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


class TTSResponse(BaseModel):
    audio_url: str
    duration_ms: int
