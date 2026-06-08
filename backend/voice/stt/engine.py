"""
Speech-to-Text Engine
Fallback chain: faster-whisper (primary) -> Lite STT (online) -> Vosk (offline fallback)
"""
import os
import tempfile
from pathlib import Path
from typing import Optional
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Global instance
_engine: Optional["STTEngine"] = None


class STTEngine:
    """Speech-to-text engine with fallback chain."""

    def __init__(self):
        self.settings = get_settings()
        self._whisper_model = None
        self._vosk_model = None
        self._initialized = False

    async def initialize(self):
        """Initialize the primary STT engine (faster-whisper)."""
        if self._initialized:
            return

        try:
            from faster_whisper import WhisperModel

            model_size = self.settings.whisper_model_size
            model_dir = Path(self.settings.whisper_model_dir)
            model_dir.mkdir(parents=True, exist_ok=True)

            self._whisper_model = WhisperModel(
                model_size,
                download_root=str(model_dir),
                device="cpu",
                compute_type="int8",
            )
            logger.info(f"faster-whisper initialized: model={model_size}")
        except ImportError:
            logger.warning("faster-whisper not installed -- will use fallback STT")
        except Exception as e:
            logger.error(f"Failed to initialize faster-whisper: {e}")

        self._initialized = True

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> dict:
        """
        Transcribe audio data using the fallback chain.

        Returns:
            {"text": str, "confidence": float, "provider": str, "error": Optional[str]}
        """
        if not self._initialized:
            await self.initialize()

        result = None
        errors = []

        # 1. Try faster-whisper
        if self._whisper_model:
            result = await self._transcribe_whisper(audio_data)
            if result and result.get("text", "").strip():
                result["provider"] = "faster-whisper"
                return result
            errors.append(f"whisper: {result.get('error', 'empty result') if result else 'not tried'}")

        # 2. Try lite STT
        try:
            result = await self._transcribe_lite(audio_data)
            if result and result.get("text", "").strip():
                result["provider"] = "lite-stt"
                return result
            errors.append(f"lite: {result.get('error', 'empty') if result else 'error'}")
        except Exception as e:
            errors.append(f"lite: {e}")

        # 3. Try vosk
        try:
            result = await self._transcribe_vosk(audio_data)
            if result and result.get("text", "").strip():
                result["provider"] = "vosk"
                return result
            errors.append(f"vosk: {result.get('error', 'empty') if result else 'error'}")
        except Exception as e:
            errors.append(f"vosk: {e}")

        return {"text": "", "confidence": 0.0, "provider": "none", "error": "; ".join(errors)}

    async def _transcribe_whisper(self, audio_data: bytes) -> dict:
        """Transcribe using faster-whisper."""
        try:
            # Write to temp file (faster-whisper needs a file path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            segments, info = self._whisper_model.transcribe(
                tmp_path,
                beam_size=5,
                language="en",
                vad_filter=True,
            )

            text = " ".join(seg.text for seg in segments)
            confidence = info.average_log_prob if info else 0.0

            os.unlink(tmp_path)

            return {"text": text.strip(), "confidence": float(max(0, confidence)), "error": None}

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    async def _transcribe_lite(self, audio_data: bytes) -> dict:
        """Transcribe using Lite STT (Google Web Speech API fallback)."""
        try:
            import speech_recognition as sr

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_path) as source:
                audio = recognizer.record(source)

            os.unlink(tmp_path)

            text = recognizer.recognize_google(audio)
            return {"text": text, "confidence": 0.8, "error": None}

        except ImportError:
            return {"text": "", "confidence": 0.0, "error": "speech_recognition not installed"}
        except sr.UnknownValueError:
            return {"text": "", "confidence": 0.0, "error": "could not understand audio"}
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}

    async def _transcribe_vosk(self, audio_data: bytes) -> dict:
        """Transcribe using Vosk (offline fallback)."""
        try:
            import json
            import wave
            import io

            import vosk

            # Initialize Vosk model if not loaded
            if self._vosk_model is None:
                model_path = os.environ.get("VOSK_MODEL_PATH", "data/vosk-model-small-en-us-0.15")
                if os.path.isdir(model_path):
                    self._vosk_model = vosk.Model(model_path)
                else:
                    return {"text": "", "confidence": 0.0, "error": "Vosk model not found"}

            # Process audio
            wf = wave.open(io.BytesIO(audio_data))
            rec = vosk.KaldiRecognizer(self._vosk_model, wf.getframerate())

            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                rec.AcceptWaveform(data)

            result = json.loads(rec.FinalResult())
            text = result.get("text", "")

            return {"text": text, "confidence": result.get("confidence", 0.0), "error": None}

        except ImportError:
            return {"text": "", "confidence": 0.0, "error": "vosk not installed"}
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}


def get_stt_engine() -> STTEngine:
    """Get or create the global STT engine singleton."""
    global _engine
    if _engine is None:
        _engine = STTEngine()
    return _engine
