"""
faster-whisper STT — offline speech recognition using faster-whisper
(CTranslate2-optimised Whisper).

Models are downloaded on first use and cached locally.
Lightweight models: tiny ~75 MB, base ~142 MB, small ~466 MB.

Select model size via WHISPER_MODEL_SIZE env var (default: "tiny").
Set WHISPER_MODEL_DIR to override the cache directory.

Usage:
    from speech.faster_whisper_stt import transcribe_wav, is_available
    text = transcribe_wav(wav_bytes)
"""
import logging, os, threading
from pathlib import Path

_log = logging.getLogger("faster_whisper_stt")

_model = None
_model_lock = threading.Lock()

MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny").strip().lower()
MODEL_DIR = os.environ.get(
    "WHISPER_MODEL_DIR",
    str(Path(__file__).parent / "faster_whisper_models"),
)


def init_model() -> bool:
    """Lazy-load the faster-whisper model. Safe to call multiple times."""
    global _model
    with _model_lock:
        if _model is not None:
            return True
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _log.warning(
                "faster-whisper package not installed — run: pip install faster-whisper"
            )
            return False

        try:
            os.makedirs(MODEL_DIR, exist_ok=True)
            _log.info(
                "Loading faster-whisper model '%s' (device=cpu, compute_type=int8) "
                "into %s …",
                MODEL_SIZE,
                MODEL_DIR,
            )
            _model = WhisperModel(
                MODEL_SIZE,
                device="cpu",
                compute_type="int8",
                download_root=MODEL_DIR,
                cpu_threads=os.cpu_count() or 2,
                num_workers=1,
            )
            _log.info("faster-whisper model '%s' ready", MODEL_SIZE)
            return True
        except Exception as exc:
            _log.warning("Failed to init faster-whisper: %s", exc)
            return False


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """Transcribe raw PCM s16le audio bytes to text."""
    if not audio_bytes:
        return ""
    if not init_model():
        return ""
    try:
        import numpy as np

        # Convert int16 PCM to float32 [-1.0, 1.0]
        audio_f32 = (
            np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        )

        segments, info = _model.transcribe(
            audio_f32,
            beam_size=1,          # faster than default 5
            language=None,         # auto-detect
            vad_filter=True,       # skip silence
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=250,
                max_speech_duration_s=30,
                min_silence_duration_ms=100,
            ),
        )
        text = " ".join(seg.text for seg in segments).strip()
        return text
    except Exception as exc:
        _log.warning("faster-whisper transcribe error: %s", exc)
        return ""


def transcribe_wav(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes to text (WAV header is parsed by faster-whisper)."""
    return transcribe(wav_bytes)


def is_available() -> bool:
    return _model is not None


def get_model_info() -> dict:
    return {
        "model": f"faster-whisper/{MODEL_SIZE}",
        "type": "offline",
        "loaded": _model is not None,
        "cache_path": MODEL_DIR,
    }
