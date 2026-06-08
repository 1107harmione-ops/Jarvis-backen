"""
Voice processing utilities: format conversion, audio slicing, noise reduction.
"""
import io
import wave
import struct
import tempfile
from pathlib import Path
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


class VoiceProcessor:
    """Audio processing utilities for voice pipeline."""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit

    @staticmethod
    def convert_to_wav(audio_data: bytes, sample_rate: int = 16000) -> Optional[bytes]:
        """Convert raw audio bytes to WAV format."""
        try:
            import soundfile as sf
            import numpy as np

            with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            data, sr = sf.read(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)

            # Resample if needed
            if sr != sample_rate:
                # Simple linear resampling
                old_len = len(data)
                new_len = int(old_len * sample_rate / sr)
                data = np.interp(
                    np.linspace(0, old_len - 1, new_len),
                    np.arange(old_len),
                    data,
                )

            # Convert to WAV
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(VoiceProcessor.CHANNELS)
                wf.setsampwidth(VoiceProcessor.SAMPLE_WIDTH)
                wf.setframerate(sample_rate)
                wf.writeframes((data * 32767).astype(np.int16).tobytes())

            return wav_buffer.getvalue()

        except ImportError:
            logger.warning("soundfile not available -- using basic WAV conversion")
            return VoiceProcessor._basic_wav_convert(audio_data, sample_rate)
        except Exception as e:
            logger.error(f"WAV conversion failed: {e}")
            return None

    @staticmethod
    def _basic_wav_convert(audio_data: bytes, sample_rate: int = 16000) -> bytes:
        """Basic WAV conversion without numpy."""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(VoiceProcessor.CHANNELS)
            wf.setsampwidth(VoiceProcessor.SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        return wav_buffer.getvalue()

    @staticmethod
    def get_audio_duration(audio_data: bytes) -> float:
        """Get duration of WAV audio in seconds."""
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / rate if rate > 0 else 0
        except Exception:
            return 0.0

    @staticmethod
    def slice_audio(audio_data: bytes, start_sec: float, end_sec: float) -> Optional[bytes]:
        """Slice a WAV file by time."""
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                rate = wf.getframerate()
                wf.setpos(int(start_sec * rate))
                frames = wf.readframes(int((end_sec - start_sec) * rate))

                out = io.BytesIO()
                with wave.open(out, "wb") as wf_out:
                    wf_out.setnchannels(wf.getnchannels())
                    wf_out.setsampwidth(wf.getsampwidth())
                    wf_out.setframerate(rate)
                    wf_out.writeframes(frames)
                return out.getvalue()
        except Exception as e:
            logger.error(f"Audio slicing failed: {e}")
            return None

    @staticmethod
    def get_audio_level(audio_data: bytes) -> float:
        """Calculate RMS audio level (0.0 - 1.0)."""
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                if not frames:
                    return 0.0
                samples = struct.unpack(f"<{len(frames) // 2}h", frames)
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                return min(1.0, rms / 32768.0)
        except Exception:
            return 0.0
