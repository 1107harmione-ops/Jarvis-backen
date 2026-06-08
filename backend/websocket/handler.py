import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from backend.websocket.manager import get_manager
from backend.websocket.protocol import WSMessage, MessageType
from backend.core.security import verify_token
from backend.core.logging import log_ws_event
from backend.core.config import get_settings


async def handle_websocket(websocket: WebSocket, token: Optional[str] = None):
    """
    Main WebSocket handler that processes all WS events.

    Protocol flow:
    1. Client connects → server sends CONNECTED
    2. If token provided, server validates and sends AUTH_SUCCESS
    3. Client sends USER_MESSAGE → server processes and responds
    4. Client sends PING → server responds with PONG
    5. Client disconnects → server cleans up
    """
    manager = get_manager()
    settings = get_settings()

    # Generate client ID
    import uuid
    client_id = uuid.uuid4().hex[:12]

    # Authenticate if token provided
    user_id = None
    if token:
        payload = verify_token(token)
        if payload:
            user_id = payload.sub

    await manager.connect(websocket, client_id, user_id)

    # Send connected message
    await manager.send_message(client_id, {
        "type": MessageType.CONNECTED.value,
        "data": {"client_id": client_id, "authenticated": user_id is not None},
        "msg_id": uuid.uuid4().hex[:12],
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg = WSMessage(**data)
            except (json.JSONDecodeError, ValueError) as e:
                await manager.send_message(client_id, {
                    "type": MessageType.ERROR.value,
                    "data": {"code": 400, "message": f"Invalid message format: {e}"},
                    "msg_id": uuid.uuid4().hex[:12],
                })
                continue

            if msg.type == MessageType.PING:
                await manager.send_message(client_id, {
                    "type": MessageType.PONG.value,
                    "data": {"timestamp": __import__("time").time()},
                    "msg_id": msg.msg_id,
                })

            elif msg.type == MessageType.USER_MESSAGE:
                await _handle_user_message(manager, client_id, msg, user_id)

            elif msg.type == MessageType.TYPING:
                await manager.send_to_user(user_id or "", {
                    "type": MessageType.TYPING_INDICATOR.value,
                    "data": msg.data,
                    "msg_id": msg.msg_id,
                })

            elif msg.type == MessageType.COMMAND:
                await _handle_command(manager, client_id, msg, user_id)

            else:
                await manager.send_message(client_id, {
                    "type": MessageType.ERROR.value,
                    "data": {"code": 400, "message": f"Unknown message type: {msg.type}"},
                    "msg_id": msg.msg_id,
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log_ws_event("error", client_id, error=str(e))
    finally:
        await manager.disconnect(client_id)


async def _handle_user_message(
    manager, client_id: str, msg: WSMessage, user_id: Optional[str]
):
    """Process a user message: call LLM and stream back response."""
    from backend.websocket.protocol import MessageType
    import uuid, time

    user_text = msg.data.get("text", "")
    conversation_id = msg.data.get("conversation_id")

    if not user_text.strip():
        await manager.send_message(client_id, {
            "type": MessageType.ERROR.value,
            "data": {"code": 400, "message": "Empty message"},
            "msg_id": msg.msg_id,
        })
        return

    # Acknowledge receipt with typing indicator
    await manager.send_message(client_id, {
        "type": MessageType.TYPING_INDICATOR.value,
        "data": {"is_typing": True},
        "msg_id": uuid.uuid4().hex[:12],
    })

    try:
        # TODO: Call LLM service here
        # For now, echo as placeholder
        await asyncio.sleep(0.5)

        # Send as streaming chunks
        reply = f"Echo: {user_text}"
        chunk_size = 20
        for i in range(0, len(reply), chunk_size):
            chunk = reply[i:i+chunk_size]
            await manager.send_message(client_id, {
                "type": MessageType.STREAM_CHUNK.value,
                "data": {
                    "content": chunk,
                    "done": False,
                    "conversation_id": conversation_id,
                },
                "msg_id": uuid.uuid4().hex[:12],
            })
            await asyncio.sleep(0.05)

        # Send final message
        await manager.send_message(client_id, {
            "type": MessageType.BOT_REPLY.value,
            "data": {
                "reply": reply,
                "conversation_id": conversation_id or "",
                "tokens_used": len(user_text) + len(reply),
            },
            "msg_id": msg.msg_id,
        })

    except Exception as e:
        await manager.send_message(client_id, {
            "type": MessageType.ERROR.value,
            "data": {"code": 500, "message": str(e)},
            "msg_id": msg.msg_id,
        })


async def _handle_command(manager, client_id: str, msg: WSMessage, user_id: Optional[str]):
    """Handle WebSocket commands like /clear, /help, etc."""
    from backend.websocket.protocol import MessageType
    import uuid

    cmd = msg.data.get("command", "").lower()
    args = msg.data.get("args", "")

    if cmd == "ping":
        await manager.send_message(client_id, {
            "type": MessageType.PONG.value,
            "data": {"pong": True, "timestamp": __import__("time").time()},
            "msg_id": msg.msg_id,
        })
    elif cmd == "help":
        await manager.send_message(client_id, {
            "type": MessageType.BOT_REPLY.value,
            "data": {"reply": "Commands: /help, /ping, /clear, /status"},
            "msg_id": msg.msg_id,
        })
    else:
        await manager.send_message(client_id, {
            "type": MessageType.ERROR.value,
            "data": {"code": 400, "message": f"Unknown command: {cmd}"},
            "msg_id": msg.msg_id,
        })
