"""
Vosk STT — fallback offline speech recognition.
No longer auto-downloads the 40 MB model at import time.
Model must already exist on disk at the expected path;
if not, init_vosk() returns False and the caller falls
back to the lite (Google Speech API) recogniser.
"""
import json, logging, threading
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "vosk_model"
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_PATH = MODEL_DIR / MODEL_NAME

_log = logging.getLogger("vosk_stt")
_vosk_model = None
_model_lock = threading.Lock()


def init_vosk():
    """Load Vosk model — only if it already exists on disk."""
    global _vosk_model
    with _model_lock:
        if _vosk_model is not None:
            return True
        if not (MODEL_PATH.exists() and (MODEL_PATH / "am").exists()):
            _log.info("Vosk model not on disk at %s — skipping (use lite STT)", MODEL_PATH)
            return False
        try:
            from vosk import Model
            _vosk_model = Model(str(MODEL_PATH))
            _log.info("Vosk model loaded successfully")
            return True
        except Exception as e:
            _log.error("Failed to init Vosk: %s", e)
            return False


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    if not audio_bytes:
        return ""
    if _vosk_model is None:
        if not init_vosk():
            return ""
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(_vosk_model, sample_rate)
    rec.SetWords(False)
    if isinstance(audio_bytes, bytes):
        rec.AcceptWaveform(audio_bytes)
    result = json.loads(rec.FinalResult())
    text = result.get("text", "").strip()
    return text


def transcribe_wav(wav_bytes: bytes) -> str:
    return transcribe(wav_bytes)


def is_available():
    return _vosk_model is not None


def get_model_info():
    return {
        "model": MODEL_NAME,
        "path": str(MODEL_PATH),
        "loaded": _vosk_model is not None,
    }
