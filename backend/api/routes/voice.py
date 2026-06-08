"""Voice routes — speech-to-text, text-to-speech, and audio file serving."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.dependencies.auth import get_current_user_optional
from backend.models.user import User
from backend.schemas.voice import STTResponse, TTSRequest, TTSResponse

router = APIRouter(prefix="/voice", tags=["voice"])

# Directory where generated audio files are stored.
AUDIO_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "generated_audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(
    audio: UploadFile,
    current_user: User = Depends(get_current_user_optional),
) -> STTResponse:
    """Transcribe an uploaded audio file to text.

    Accepts common audio formats (wav, mp3, ogg, m4a). The actual STT
    engine integration will be connected in a future release.
    """
    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file provided",
        )

    # Validate file extension
    allowed_extensions = {".wav", ".mp3", ".ogg", ".m4a", ".webm"}
    ext = Path(audio.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{ext}'. Allowed: {', '.join(allowed_extensions)}",
        )

    # TODO: Integrate actual STT engine (faster-whisper / vosk / lite)
    # For now return a placeholder response.
    return STTResponse(
        text="[STT placeholder — audio transcription will be implemented]",
        confidence=0.0,
        provider="placeholder",
    )


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    payload: TTSRequest,
    current_user: User = Depends(get_current_user_optional),
) -> TTSResponse:
    """Convert text to speech and return the URL of the generated audio file.

    The actual TTS engine (espeak / piper / Coqui) will be connected in a
    future release.
    """
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty",
        )

    # TODO: Integrate actual TTS engine
    # Generate a placeholder file to demonstrate the audio serving pipeline.
    placeholder_filename = f"placeholder_{abs(hash(payload.text)) % 10**8}.wav"
    placeholder_path = AUDIO_DIR / placeholder_filename

    if not placeholder_path.exists():
        # Create a minimal valid WAV header (silent audio)
        _create_silent_wav(placeholder_path)

    return TTSResponse(
        audio_url=f"/voice/audio/{placeholder_filename}",
        duration_ms=0,
    )


@router.get("/audio/{filename:path}")
async def serve_audio(filename: str) -> FileResponse:
    """Serve a generated audio file."""
    file_path = AUDIO_DIR / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=filename,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _create_silent_wav(path: Path, sample_rate: int = 16000, duration_sec: int = 1) -> None:
    """Create a minimal valid WAV file containing silence.

    This is a placeholder until a real TTS engine is connected.
    """
    import struct
    import wave

    num_samples = sample_rate * duration_sec

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_samples}h", *([0] * num_samples)))
