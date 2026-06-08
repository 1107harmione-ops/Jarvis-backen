"""
Text-to-Speech Engine
Supports: espeak (Linux), pyttsx3 (Windows), gTTS (cloud fallback)
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

_engine: Optional["TTSEngine"] = None


class TTSEngine:
    """Text-to-speech engine with multiple backends."""

    AUDIO_DIR = Path("generated_audio")

    def __init__(self):
        self.settings = get_settings()
        self.AUDIO_DIR.mkdir(exist_ok=True)

    async def speak(self, text: str, voice: Optional[str] = None) -> dict:
        """
        Convert text to speech. Returns audio file info.

        Returns:
            {"filename": str, "filepath": str, "duration_ms": int, "format": str}
        """
        import uuid

        filename = f"tts_{uuid.uuid4().hex[:12]}.wav"
        filepath = self.AUDIO_DIR / filename

        engine = self.settings.tts_engine

        if engine == "espeak":
            success = await self._speak_espeak(text, str(filepath), voice)
        elif engine == "gtts":
            success = await self._speak_gtts(text, str(filepath))
        elif engine == "pyttsx3":
            success = await self._speak_pyttsx3(text, str(filepath))
        else:
            # Auto-detect: try espeak first, then gTTS
            success = await self._speak_espeak(text, str(filepath), voice)
            if not success:
                success = await self._speak_gtts(text, str(filepath))

        if not success:
            return {
                "error": "All TTS engines failed",
                "filename": "",
                "filepath": "",
                "duration_ms": 0,
                "format": "",
            }

        # Estimate duration (~10 characters per second)
        duration_ms = int((len(text) / 10) * 1000)

        logger.info(f"TTS generated: {filename} ({duration_ms}ms)")
        return {
            "filename": filename,
            "filepath": str(filepath),
            "duration_ms": duration_ms,
            "format": "wav",
        }

    async def _speak_espeak(self, text: str, output_path: str, voice: Optional[str] = None) -> bool:
        """Use espeak-ng to generate speech."""
        try:
            voice = voice or self.settings.tts_voice
            speed = self.settings.tts_speed

            cmd = [
                "espeak-ng",
                "-v", voice,
                "-s", str(speed),
                "-w", output_path,
                text,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                # Fall back to espeak
                cmd[0] = "espeak"
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )

            return result.returncode == 0 and os.path.exists(output_path)

        except FileNotFoundError:
            logger.warning("espeak/espeak-ng not found")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("espeak timed out")
            return False
        except Exception as e:
            logger.error(f"espeak failed: {e}")
            return False

    async def _speak_gtts(self, text: str, output_path: str) -> bool:
        """Use Google Text-to-Speech as fallback."""
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(output_path)
            return os.path.exists(output_path)
        except ImportError:
            logger.warning("gTTS not installed")
            return False
        except Exception as e:
            logger.error(f"gTTS failed: {e}")
            return False

    async def _speak_pyttsx3(self, text: str, output_path: str) -> bool:
        """Use pyttsx3 (Windows/local TTS)."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return os.path.exists(output_path)
        except ImportError:
            return False
        except Exception as e:
            logger.error(f"pyttsx3 failed: {e}")
            return False

    def get_available_engines(self) -> list[str]:
        """Detect which TTS engines are available."""
        available = []

        # Check espeak
        try:
            subprocess.run(["espeak-ng", "--version"], capture_output=True, timeout=5)
            available.append("espeak-ng")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                subprocess.run(["espeak", "--version"], capture_output=True, timeout=5)
                available.append("espeak")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # Check gTTS
        try:
            import gtts  # noqa: F401
            available.append("gtts")
        except ImportError:
            pass

        return available


def get_tts_engine() -> TTSEngine:
    """Get or create the global TTS engine singleton."""
    global _engine
    if _engine is None:
        _engine = TTSEngine()
    return _engine
