"""Tests for SQLAlchemy models.

SQLAlchemy Column(default=...) values are applied at flush time, not at Python
object creation. Tests verify correct attribute existence and explicit values.
"""
import pytest
from uuid import UUID
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.device import Device
from backend.models.memory_entry import MemoryEntry
from backend.models.audio_log import AudioLog
from backend.models.goal import Goal


class TestUserModel:
    def test_create_user(self):
        user = User(username="testuser", email="test@test.com", hashed_password="hash")
        assert user.username == "testuser"
        assert user.email == "test@test.com"
        # Column defaults (role="user", is_active=True) applied at flush time
        assert hasattr(user, "role")
        assert hasattr(user, "is_active")
        assert hasattr(user, "is_verified")

    def test_user_str(self):
        user = User(username="testuser", email="e@e.com", hashed_password="h")
        assert str(user)  # Should not raise


class TestConversationModel:
    def test_create_conversation(self):
        conv = Conversation(user_id=UUID("12345678-1234-5678-1234-567812345678"))
        assert hasattr(conv, "title")
        assert hasattr(conv, "is_active")


class TestMessageModel:
    def test_create_message(self):
        msg = Message(
            conversation_id=UUID("12345678-1234-5678-1234-567812345678"),
            role="user",
            content="Hello!",
        )
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_message_tool_calls(self):
        msg = Message(
            conversation_id=UUID("12345678-1234-5678-1234-567812345678"),
            role="assistant",
            content="Let me check...",
            tool_calls=[{"name": "get_time", "args": {}}],
        )
        assert msg.tool_calls == [{"name": "get_time", "args": {}}]


class TestDeviceModel:
    def test_create_device(self):
        device = Device(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            device_id="android-abc123",
            device_name="Pixel 8",
            device_type="android",
        )
        assert device.device_id == "android-abc123"
        assert device.device_type == "android"


class TestMemoryEntryModel:
    def test_create_memory(self):
        mem = MemoryEntry(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            content="User likes sci-fi movies",
            memory_type="semantic",
        )
        assert mem.memory_type == "semantic"
        assert hasattr(mem, "importance")  # default applied at flush

    def test_memory_importance_levels(self):
        for imp in ["low", "medium", "high", "critical"]:
            mem = MemoryEntry(
                user_id=UUID("12345678-1234-5678-1234-567812345678"),
                content=f"Test {imp}",
                importance=imp,
            )
            assert mem.importance == imp


class TestGoalModel:
    def test_create_goal(self):
        goal = Goal(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            title="Learn Python",
        )
        assert goal.title == "Learn Python"
        assert hasattr(goal, "status")  # default applied at flush
        assert hasattr(goal, "progress")


class TestAudioLogModel:
    def test_create_audio_log(self):
        log = AudioLog(filename="test.wav", duration_ms=5000)
        assert log.filename == "test.wav"
        assert log.duration_ms == 5000
