"""Tests for WebSocket protocol and messages."""
import pytest
from backend.websocket.protocol import WSMessage, MessageType


class TestWSMessage:
    def test_create_message(self):
        msg = WSMessage(type=MessageType.USER_MESSAGE, data={"text": "hello"})
        assert msg.type == MessageType.USER_MESSAGE
        assert msg.data["text"] == "hello"
        assert len(msg.msg_id) == 12  # auto-generated

    def test_auto_msg_id(self):
        msg1 = WSMessage(type=MessageType.PING)
        msg2 = WSMessage(type=MessageType.PING)
        assert msg1.msg_id != msg2.msg_id  # unique IDs

    def test_custom_msg_id(self):
        msg = WSMessage(type=MessageType.PING, msg_id="custom123")
        assert msg.msg_id == "custom123"

    def test_default_data(self):
        msg = WSMessage(type=MessageType.CONNECTED)
        assert msg.data == {}


class TestMessageType:
    def test_all_types_present(self):
        """Verify that MessageType has all expected values."""
        assert MessageType.USER_MESSAGE.value == "user_message"
        assert MessageType.PING.value == "ping"
        assert MessageType.BOT_REPLY.value == "bot_reply"
        assert MessageType.STREAM_CHUNK.value == "stream_chunk"
        assert MessageType.ERROR.value == "error"
        assert MessageType.CONNECTED.value == "connected"

    def test_all_message_types_unique(self):
        types = list(MessageType)
        values = [t.value for t in types]
        assert len(values) == len(set(values))
