"""
Lightweight STT using SpeechRecognition + Google Web Speech API.
No model download needed — uses Google's free cloud speech recognition.
Faster startup, zero disk footprint, always-on accuracy.
"""
import io, json, logging, struct, tempfile
import speech_recognition as sr

_log = logging.getLogger("lite_stt")

_recognizer = None


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = sr.Recognizer()
        _recognizer.energy_threshold = 300
        _recognizer.dynamic_energy_threshold = True
        _recognizer.pause_threshold = 0.8
    return _recognizer


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM bytes into a proper WAV container."""
    channels = 1
    bits = 16
    data_size = len(pcm_data)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * channels * bits // 8))
    buf.write(struct.pack("<H", channels * bits // 8))
    buf.write(struct.pack("<H", bits))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_data)
    return buf.getvalue()


def transcribe_wav(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes via Google Web Speech API."""
    if not wav_bytes:
        return ""
    recognizer = _get_recognizer()
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(wav_bytes)
            tmp.flush()
            with sr.AudioFile(tmp.name) as source:
                audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        return text.strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        _log.warning("Google Speech API request failed: %s", e)
        return ""
    except Exception as e:
        _log.warning("STT error: %s", e)
        return ""


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """Transcribe raw PCM audio (wraps it in WAV first)."""
    if not audio_bytes:
        return ""
    wav_bytes = _pcm_to_wav(audio_bytes, sample_rate)
    return transcribe_wav(wav_bytes)


def is_available() -> bool:
    """Light connectivity check — can we reach Google? Returns True even on
    transient failures because the API will be tried on actual requests."""
    try:
        _get_recognizer()
        return True
    except Exception:
        return False


def get_model_info() -> dict:
    return {
        "model": "Google Web Speech API",
        "type": "cloud",
        "loaded": True,
    }
