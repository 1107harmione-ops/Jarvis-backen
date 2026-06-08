"""Tests for voice system."""
import pytest
from backend.voice.stt.engine import STTEngine
from backend.voice.tts.engine import TTSEngine


class TestSTTEngine:
    @pytest.mark.asyncio
    async def test_empty_audio(self):
        engine = STTEngine()
        result = await engine.transcribe(b"")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        engine = STTEngine()
        assert not engine._initialized
        await engine.initialize()
        # May or may not find whisper, but shouldn't crash
        assert engine._initialized


class TestTTSEngine:
    @pytest.mark.asyncio
    async def test_speak_empty_text(self):
        engine = TTSEngine()
        result = await engine.speak("")
        # Should either succeed with empty audio or return error
        assert isinstance(result, dict)

    def test_available_engines(self):
        engine = TTSEngine()
        engines = engine.get_available_engines()
        assert isinstance(engines, list)
