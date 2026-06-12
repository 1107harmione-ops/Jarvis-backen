"""app_fastapi.py — FastAPI backend for JARVIS V3.

Replaces the Flask app.py with an async ASGI application.
All existing core modules reused unchanged.
"""

import sys, os, json, logging, time, re, signal, base64
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("jarvis-fastapi")

from config import PORT, GROQ_CHAT_API_KEY

if not GROQ_CHAT_API_KEY:
    raise RuntimeError("GROQ_CHAT_API_KEY not set! Add it to environment.")

# ── FastAPI ──
from fastapi import FastAPI, Request, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

# ── Simple in-memory rate limiter (replaces slowapi dependency) ──
# For production, add rate limiting at the reverse proxy (nginx/Caddy) level.
from collections import defaultdict
import asyncio

_rate_limit_store: dict = {}
_rate_limit_lock = asyncio.Lock()

async def check_rate_limit(key: str = "default", max_requests: int = 20, window: int = 60) -> bool:
    """Simple sliding window rate limiter. Returns True if allowed."""
    global _rate_limit_store
    now = time.time()
    window_num = int(now / window)
    window_key = f"{key}:{window_num}"
    async with _rate_limit_lock:
        count = _rate_limit_store.get(window_key, 0)
        if count >= max_requests:
            return False
        _rate_limit_store[window_key] = count + 1
        # Cleanup: remove entries more than 2 windows old
        for wk in list(_rate_limit_store.keys()):
            try:
                wk_window = int(wk.rsplit(":", 1)[-1])
                if wk_window < window_num - 2:
                    del _rate_limit_store[wk]
            except (ValueError, IndexError):
                continue
        return True

# ── Core Imports ──
from core.orchestrator import Orchestrator, load_training_data
from core.data_center import DataCenter
from core.auto_skill import SkillLibrary
from core.memory import Memory

_orchestrator = Orchestrator()
_memory = Memory()
_kb = DataCenter()
_skills = SkillLibrary()
_training_knowledge, _training_sources = load_training_data()

# ── V3 Module Imports ──
from core.provider_manager import get_provider_manager
from core.goal_manager import GoalManager
from core.tool_registry import ToolRegistry, discover_tools

_goal_manager = None
_tool_registry = None

def _get_goal_manager():
    global _goal_manager
    if _goal_manager is None:
        _goal_manager = GoalManager()
    return _goal_manager

def _get_tool_registry():
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        try:
            discover_tools("tools")
        except Exception as e:
            logger.warning("Tool discovery: %s", e)
    return _tool_registry

from admin.routes import admin_bp, init_admin
from admin.auth import cleanup_tokens
# Admin routes not ported to FastAPI; use Flask app.py for admin panel.
# init_admin(memory_instance=_memory, kb_instance=_kb)
cleanup_tokens()

# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JARVIS V3 FastAPI starting...")
    logger.info("Providers loaded: %d", len(get_provider_manager().providers))
    yield
    logger.info("JARVIS V3 FastAPI shutting down.")

# ── App Setup ──
app = FastAPI(
    title="JARVIS V3 API",
    description="Autonomous AI Assistant Backend",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "capacitor://localhost",
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.2.2",
    ],
    # NOTE: allow_origin_regex=".*" was removed — it bypassed the whitelist
    # and combined with allow_credentials=True created a security vulnerability.
    allow_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
)

# Static files & templates
static_dir = os.path.join(os.path.dirname(__file__), "web")
templates = Jinja2Templates(directory=static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ═══════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════

# ─── Health / Status ───

@app.get("/health")
async def health():
    providers = {}
    try:
        providers = get_provider_manager().health_status()
    except Exception:
        pass
    return {
        "status": "online",
        "platform": "render",
        "port": PORT,
        "version": "3.0",
        "providers": providers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    return templates.TemplateResponse(request=request, name="knowledge.html")


# ─── Chat ───

@app.post("/chat")
async def chat_process(request: Request):
    # Simple rate limit: 20 req/min per IP
    try:
        ip = request.client.host if request.client else "unknown"
    except Exception:
        ip = "unknown"
    if not await check_rate_limit(f"chat:{ip}", max_requests=20, window=60):
        return JSONResponse(status_code=429, content={"reply": "Rate limit exceeded. Please slow down.", "error": "rate_limited"})
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    message = str(data.get("message", "")).strip()
    if not message:
        return JSONResponse(content={"reply": "I didn't hear anything."})
    try:
        result = _orchestrator.run(message)
        response = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        elapsed_ms = result.get("time_ms", 0)
        logger.info("Chat | agent=%s | time=%dms | msg=%s", agent_used, elapsed_ms, str(message)[:80])
        return {
            "reply": str(response),
            "agent": agent_used,
            "image_url": metadata.get("image_url"),
            "filepath": metadata.get("filepath"),
            "sources": metadata.get("sources"),
            "execution_output": metadata.get("execution_output"),
            "task": metadata.get("task"),
            "target": metadata.get("target"),
            "compound_execution": metadata.get("compound_execution"),
            "time_ms": elapsed_ms,
            "training_entries": len(_training_knowledge),
            "training_sources": len(_training_sources),
            "status": "success" if result.get("success", True) else "error",
        }
    except Exception as e:
        logger.error("Chat error: %s", e)
        return JSONResponse(content={"error": str(e), "reply": "I encountered a neural link error."})


# ─── Agent ───

@app.post("/agent")
async def agent_direct(request: Request):
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    message = data.get("message", "").strip()
    agent_name = data.get("agent", "").strip()
    if not message:
        return JSONResponse(content={"error": "message required"})
    try:
        if agent_name:
            from agents import CodingAgent, ImageAgent, TaskAgent, ResearchAgent, SearchAgent, ReasoningAgent
            agent_map = {
                "coding": CodingAgent, "image": ImageAgent, "task": TaskAgent,
                "research": ResearchAgent, "search": SearchAgent, "reasoning": ReasoningAgent,
            }
            cls = agent_map.get(agent_name.lower())
            if cls:
                result = cls().run(message, data.get("parameters", {}))
                return {
                    "reply": result.get("result", ""),
                    "agent": result.get("agent"),
                    "metadata": result.get("metadata", {}),
                    "status": "success" if result.get("success") else "error",
                }
            return JSONResponse(content={"error": f"Unknown agent: {agent_name}"})
        else:
            result = _orchestrator.run(message)
            return {
                "reply": result.get("response", ""),
                "agent": result.get("agent"),
                "metadata": result.get("metadata", {}),
                "time_ms": result.get("time_ms", 0),
                "status": "success" if result.get("success") else "error",
            }
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


@app.get("/agents")
async def list_agents():
    return _orchestrator.list_agents()


@app.get("/history")
async def get_history():
    return _memory.get_recent_chat(20)


@app.get("/status")
async def get_stats():
    import platform
    system = f"FastAPI | Render Cloud | Python {platform.python_version()} | {platform.machine()}"
    kb_stats = _kb.stats()
    return {
        "status": "online",
        "platform": "render",
        "version": "3.0",
        "time": datetime.now().strftime("%I:%M %p, %A %B %d, %Y"),
        "system": system,
        "training_entries": len(_training_knowledge),
        "training_sources": len(_training_sources),
        "knowledge_entries": kb_stats["total_entries"],
        "knowledge_categories": len(kb_stats["entries_by_category"]),
    }


@app.post("/training/refresh")
async def refresh_training():
    global _training_knowledge, _training_sources
    _training_knowledge, _training_sources = load_training_data()
    return {"status": "success", "training_entries": len(_training_knowledge), "training_sources": len(_training_sources)}


# ─── Speech Recognition ───
_stt_mode = "none"
transcribe_wav = None

# 1) faster-whisper
try:
    from speech.faster_whisper_stt import (
        transcribe_wav as fw_transcribe_wav,
        is_available as fw_available,
        init_model as fw_init,
    )
    if fw_init():
        transcribe_wav = fw_transcribe_wav
        _stt_mode = "faster-whisper"
        logger.info("STT: faster-whisper loaded (offline)")
    else:
        logger.info("STT: faster-whisper model not cached — lazy-load on first request")
        transcribe_wav = fw_transcribe_wav
        _stt_mode = "faster-whisper-lazy"
except ImportError:
    logger.info("STT: faster-whisper not installed, skipping")
except Exception as e:
    logger.warning("STT: faster-whisper init warning: %s", e)

# 2) Lite fallback
try:
    from speech.lite_stt import transcribe_wav as lite_transcribe_wav
    if _stt_mode == "none":
        transcribe_wav = lite_transcribe_wav
        _stt_mode = "lite"
        logger.info("STT: Lite (Google Web Speech API)")
    else:
        _lite_transcribe_wav = lite_transcribe_wav
        logger.info("STT: Lite available as fallback")
except Exception as e:
    logger.warning("STT: Lite init failed: %s", e)

# 3) Vosk fallback
_vosk_ready = False
try:
    from speech.vosk_stt import init_vosk
    _vosk_ready = init_vosk()
    if _vosk_ready:
        logger.info("STT: Vosk fallback available")
except Exception:
    pass


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if transcribe_wav is None:
        return JSONResponse(content={"error": "STT not available on this server", "text": ""})
    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse(content={"error": "Empty audio", "text": ""})
    try:
        text = transcribe_wav(audio_bytes)
        if not text:
            # Use globals() — _lite_transcribe_wav is a module-level variable, not local
            if _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
                text = globals()["_lite_transcribe_wav"](audio_bytes)
            if not text and _vosk_ready:
                from speech.vosk_stt import transcribe_wav as vosk_fallback
                text = vosk_fallback(audio_bytes)
        return {"text": text or "", "error": ""}
    except Exception as e:
        logger.error("Transcribe error: %s", e)
        return JSONResponse(content={"error": str(e), "text": ""}, status_code=500)


@app.post("/transcribe/json")
async def transcribe_json(request: Request):
    if transcribe_wav is None:
        return JSONResponse(content={"error": "STT not available on this server", "text": ""})
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    audio_b64 = data.get("audio", "")
    if not audio_b64:
        return JSONResponse(content={"error": "No audio data", "text": ""})
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return JSONResponse(content={"error": "Invalid base64", "text": ""})
    try:
        text = transcribe_wav(audio_bytes)
        if not text:
            if _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
                text = globals()["_lite_transcribe_wav"](audio_bytes)
            if not text and _vosk_ready:
                from speech.vosk_stt import transcribe_wav as vosk_fallback
                text = vosk_fallback(audio_bytes)
        return {"text": text or "", "error": ""}
    except Exception as e:
        logger.error("Transcribe JSON error: %s", e)
        return JSONResponse(content={"error": str(e), "text": ""}, status_code=500)


@app.get("/transcribe/status")
async def transcribe_status():
    info = {"mode": _stt_mode, "vosk_available": _vosk_ready}
    try:
        if _stt_mode.startswith("faster-whisper"):
            from speech.faster_whisper_stt import is_available, get_model_info
            info["available"] = is_available()
            info["model"] = get_model_info()
        else:
            from speech.lite_stt import is_available, get_model_info
            info["available"] = is_available()
            info["model"] = get_model_info()
    except Exception:
        info["available"] = transcribe_wav is not None
        info["model"] = {}
    return info



# ─── Voice Chat (Button-Triggered, No Wake Word) ─────────────────────────────
# Flow: User taps button → records until silence/button release
#       → client sends audio here → server transcribes → orchestrator → reply
# No wake word: recording only begins when user explicitly presses the button.
# ─────────────────────────────────────────────────────────────────────────────

def _do_transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio bytes with full fallback chain (faster-whisper → lite → vosk)."""
    if transcribe_wav is None:
        return ""
    text = transcribe_wav(audio_bytes)
    if not text and _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
        text = globals()["_lite_transcribe_wav"](audio_bytes)
    if not text and _vosk_ready:
        from speech.vosk_stt import transcribe_wav as vosk_fallback
        text = vosk_fallback(audio_bytes)
    return text or ""


@app.post("/voice-chat")
async def voice_chat(request: Request, file: UploadFile = File(...)):
    """
    Button-triggered voice chat — multipart audio file upload.

    No wake word. Recording starts only when the user taps the button.

    Client flow:
      1. User taps MIC button  →  start recording
      2. Silence detected or user releases button  →  stop recording
      3. POST audio file to this endpoint
      4. Receive {transcript, reply, agent, ...} in one response

    Accepts: WAV, WebM, OGG, MP3, M4A
    """
    try:
        ip = request.client.host if request.client else "unknown"
    except Exception:
        ip = "unknown"
    if not await check_rate_limit(f"voice:{ip}", max_requests=30, window=60):
        return JSONResponse(status_code=429, content={
            "error": "Rate limit exceeded. Please wait a moment.",
            "transcript": "", "reply": "Too many requests."
        })

    if transcribe_wav is None:
        return JSONResponse(status_code=503, content={
            "error": "Speech recognition not available on this server.",
            "transcript": "", "reply": ""
        })

    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse(status_code=400, content={
            "error": "Empty audio file received.", "transcript": "", "reply": ""
        })

    start = time.time()

    # Step 1: Transcribe
    try:
        transcript = _do_transcribe(audio_bytes)
    except Exception as e:
        logger.error("voice-chat transcribe error: %s", e)
        return JSONResponse(status_code=500, content={
            "error": f"Transcription failed: {e}", "transcript": "", "reply": ""
        })

    if not transcript or not transcript.strip():
        return {
            "transcript": "",
            "reply": "I didn't catch that. Please tap the button and speak again.",
            "agent": "stt",
            "metadata": {},
            "time_ms": int((time.time() - start) * 1000),
            "status": "no_speech",
            "error": "",
        }

    logger.info("voice-chat | transcript=%s", transcript[:80])

    # Step 2: Process through orchestrator
    try:
        result = _orchestrator.run(transcript.strip())
        reply = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("voice-chat | agent=%s time=%dms", agent_used, elapsed_ms)
        return {
            "transcript": transcript,
            "reply": str(reply),
            "agent": agent_used,
            "image_url": metadata.get("image_url"),
            "filepath": metadata.get("filepath"),
            "sources": metadata.get("sources"),
            "execution_output": metadata.get("execution_output"),
            "task": metadata.get("task"),
            "target": metadata.get("target"),
            "compound_execution": metadata.get("compound_execution"),
            "metadata": metadata,
            "time_ms": elapsed_ms,
            "status": "success" if result.get("success", True) else "error",
            "error": "",
        }
    except Exception as e:
        logger.error("voice-chat orchestrator error: %s", e)
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "transcript": transcript,
            "reply": "I encountered an error processing your request.",
        })


@app.post("/voice-chat/json")
async def voice_chat_json(request: Request):
    """
    Button-triggered voice chat — JSON body with base64-encoded audio.
    Ideal for Flutter, React Native, or web apps.

    Body:
      { "audio": "<base64-encoded WAV/WebM>", "session_id": "optional" }

    Returns same shape as POST /voice-chat.
    """
    try:
        ip = request.client.host if request.client else "unknown"
    except Exception:
        ip = "unknown"
    if not await check_rate_limit(f"voice:{ip}", max_requests=30, window=60):
        return JSONResponse(status_code=429, content={
            "error": "Rate limit exceeded.", "transcript": "", "reply": "Too many requests."
        })

    if transcribe_wav is None:
        return JSONResponse(status_code=503, content={
            "error": "Speech recognition not available.", "transcript": "", "reply": ""
        })

    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
        else:
            data = {}
    except Exception:
        data = {}

    audio_b64 = data.get("audio", "").strip()
    session_id = data.get("session_id", "").strip()

    if not audio_b64:
        return JSONResponse(status_code=400, content={
            "error": "No audio provided. Send base64-encoded audio in the 'audio' field.",
            "transcript": "", "reply": ""
        })

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return JSONResponse(status_code=400, content={
            "error": "Invalid base64 audio data.", "transcript": "", "reply": ""
        })

    if not audio_bytes:
        return JSONResponse(status_code=400, content={
            "error": "Empty audio after decoding.", "transcript": "", "reply": ""
        })

    start = time.time()

    # Step 1: Transcribe
    try:
        transcript = _do_transcribe(audio_bytes)
    except Exception as e:
        logger.error("voice-chat/json transcribe error: %s", e)
        return JSONResponse(status_code=500, content={
            "error": f"Transcription failed: {e}", "transcript": "", "reply": ""
        })

    if not transcript or not transcript.strip():
        return {
            "transcript": "",
            "reply": "I didn't catch that. Please tap the button and speak again.",
            "agent": "stt",
            "metadata": {},
            "time_ms": int((time.time() - start) * 1000),
            "status": "no_speech",
            "error": "",
        }

    logger.info("voice-chat/json | transcript=%s", transcript[:80])

    # Step 2: Process through orchestrator
    try:
        result = _orchestrator.run(transcript.strip(), session_id=session_id)
        reply = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("voice-chat/json | agent=%s time=%dms", agent_used, elapsed_ms)
        return {
            "transcript": transcript,
            "reply": str(reply),
            "agent": agent_used,
            "image_url": metadata.get("image_url"),
            "filepath": metadata.get("filepath"),
            "sources": metadata.get("sources"),
            "execution_output": metadata.get("execution_output"),
            "task": metadata.get("task"),
            "target": metadata.get("target"),
            "compound_execution": metadata.get("compound_execution"),
            "metadata": metadata,
            "time_ms": elapsed_ms,
            "status": "success" if result.get("success", True) else "error",
            "error": "",
        }
    except Exception as e:
        logger.error("voice-chat/json orchestrator error: %s", e)
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "transcript": transcript,
            "reply": "I encountered an error processing your request.",
        })


@app.get("/voice-chat/status")
async def voice_chat_status():
    """Check if button-triggered voice chat is available on this server."""
    stt_ready = transcribe_wav is not None
    return {
        "available": stt_ready,
        "stt_mode": _stt_mode,
        "vosk_fallback": _vosk_ready,
        "wake_word_enabled": False,
        "mode": "button_triggered",
        "endpoints": {
            "file_upload": "POST /voice-chat       (multipart/form-data, field: file)",
            "base64_json": "POST /voice-chat/json  (application/json,    field: audio)",
            "status":      "GET  /voice-chat/status",
        },
        "message": (
            "Ready. Tap button to start, speak, stop recording — reply returned instantly."
            if stt_ready else
            "STT engine not loaded. Check server logs."
        ),
    }


# ─── Knowledge ───

@app.post("/knowledge/search")
async def knowledge_search(request: Request):
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    query = data.get("query", "").strip()
    if not query:
        return JSONResponse(content={"error": "query required", "results": []})
    category = data.get("category")
    limit = data.get("limit", 10)
    results = _kb.search(query, category=category, limit=limit)
    return {"results": results, "total": len(results)}

@app.get("/knowledge/stats")
async def knowledge_stats():
    return _kb.stats()

@app.get("/knowledge/categories")
async def knowledge_categories():
    return _kb.get_categories()

@app.get("/knowledge/entry")
async def knowledge_entry(id: str = ""):
    if not id:
        return JSONResponse(content={"error": "id parameter required"})
    try:
        entry = _kb.get_entry(int(id))
        if not entry:
            return JSONResponse(content={"error": "entry not found"})
        return entry
    except ValueError:
        return JSONResponse(content={"error": "invalid id"})

@app.get("/knowledge/random")
async def knowledge_random(count: int = 3):
    count = max(1, min(count, 20))
    return {"results": _kb.random_entries(count=count)}


# ─── Auto-Skills ───

@app.get("/auto-skills")
async def auto_skills_list():
    return {"skills": _skills.get_all(), "count": len(_skills.get_all())}

@app.post("/auto-skills/search")
async def auto_skills_search(request: Request):
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
        else:
            data = {}
    except Exception:
        data = {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    query = data.get("query", "").strip()
    if not query:
        return {"skills": [], "count": 0}
    return {"skills": _skills.get_relevant(query, limit=5)}

@app.get("/auto-skills/{skill_id}")
async def auto_skills_get(skill_id: str):
    skill = _skills.get_by_id(skill_id)
    if not skill:
        return JSONResponse(content={"error": "skill not found"})
    return skill


# ─── Shutdown ───

@app.post("/shutdown")
async def shutdown_backend(request: Request):
    shutdown_token = os.environ.get("JARVIS_SHUTDOWN_TOKEN", "").strip()
    if not shutdown_token:
        return JSONResponse(content={"error": "shutdown disabled"}, status_code=503)
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
    except Exception:
        data = {}
    token = data.get("token", "")
    if token != shutdown_token:
        return JSONResponse(content={"error": "invalid token"}, status_code=403)
    logger.info("Shutdown requested — terminating gracefully")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}


# ─── Memory / Sessions ───

@app.post("/memory/save")
async def memory_save(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    session_id = data.get("session_id", "")
    preview = data.get("preview", "")
    name = data.get("name", "")
    if session_id:
        _memory.create_session(session_id, name)
        _memory.update_session(session_id, preview=preview, count=0)
        return {"status": "saved", "session_id": session_id}
    return {"status": "ok"}

@app.get("/sessions")
async def list_sessions(limit: int = 20):
    sessions = _memory.get_sessions(limit=limit)
    return {"sessions": sessions}

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    messages = _memory.get_session_messages(session_id)
    return {"messages": messages}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    _memory.delete_session(session_id)
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════════
# V3 API ROUTES
# ═══════════════════════════════════════════════════════════════════

# ─── Planner ───

@app.post("/v3/plan")
async def v3_plan(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    goal = data.get("goal", "").strip()
    if not goal:
        return JSONResponse(content={"error": "goal required", "tasks": []})
    try:
        tasks = _orchestrator.run_plan(goal, data.get("context"))
        return {"goal": goal, "tasks": tasks, "task_count": len(tasks)}
    except Exception as e:
        logger.error("V3 plan error: %s", e)
        return JSONResponse(content={"error": str(e), "tasks": []})


# ─── Goal / Workflow ───

@app.post("/v3/goal")
async def v3_create_goal(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    description = data.get("description", "").strip()
    if not description:
        return JSONResponse(content={"error": "description required"})
    try:
        goal = _get_goal_manager().create_goal(description, data.get("context"))
        goal_id = goal.id if hasattr(goal, "id") else goal.get("goal_id", "")
        return {"goal_id": goal_id, "description": description, "status": "created"}
    except Exception as e:
        logger.error("V3 create goal error: %s", e)
        return JSONResponse(content={"error": str(e)})

@app.post("/v3/goal/run")
async def v3_run_goal(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    description = data.get("description", "").strip()
    if not description:
        return JSONResponse(content={"error": "description required"})
    try:
        result = _orchestrator.run_goal(description, data.get("context"))
        return result
    except Exception as e:
        logger.error("V3 run goal error: %s", e)
        return JSONResponse(content={"error": str(e)})

@app.get("/v3/goals")
async def v3_list_goals(status: Optional[str] = None, limit: int = 20):
    try:
        goals = _get_goal_manager().list_goals(status=status, limit=limit)
        return {"goals": goals, "count": len(goals)}
    except Exception as e:
        return JSONResponse(content={"error": str(e), "goals": []})

@app.get("/v3/goals/{goal_id}")
async def v3_get_goal(goal_id: str):
    try:
        goal = _get_goal_manager().get_goal(goal_id)
        if not goal:
            return JSONResponse(content={"error": "goal not found"})
        return goal
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


# ─── Tools ───

@app.get("/v3/tools")
async def v3_list_tools():
    try:
        registry = _get_tool_registry()
        tools = registry.list_tools()
        return {"tools": tools, "count": len(tools)}
    except Exception as e:
        return JSONResponse(content={"error": str(e), "tools": []})

@app.post("/v3/tools/execute")
async def v3_execute_tool(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    tool = data.get("tool", "").strip()
    params = data.get("parameters", {})
    if not tool:
        return JSONResponse(content={"error": "tool name required"})
    try:
        result = _orchestrator.run_tool(tool, params)
        return result
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


# ─── Provider ───

@app.get("/v3/provider/health")
async def v3_provider_health():
    try:
        health = _orchestrator.get_provider_health()
        return {"providers": health}
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@app.get("/v3/provider/stats")
async def v3_provider_stats():
    try:
        pm = get_provider_manager()
        stats = pm.get_provider_stats()
        return {"providers": stats}
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


# ─── Verifier ───

@app.post("/v3/verify")
async def v3_verify(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    task = data.get("task", {})
    result = data.get("result", {})
    if not task:
        return JSONResponse(content={"error": "task required"})
    try:
        verification = _orchestrator.verify_result(task, result)
        return verification
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


# ─── Memory V3 ───

@app.get("/v3/memory/stats")
async def v3_memory_stats():
    try:
        from memory.database_memory import DatabaseMemory
        from memory.vector_memory import VectorMemory
        db = DatabaseMemory()
        vec = VectorMemory()
        return {"database_memory": True, "vector_memory": {"count": vec.count()}}
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@app.post("/v3/memory/store")
async def v3_memory_store(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()
    if not key or not value:
        return JSONResponse(content={"error": "key and value required"})
    try:
        from memory.database_memory import DatabaseMemory
        db = DatabaseMemory()
        db.store_fact(key, value, data.get("category", "general"), data.get("importance", 1))
        return {"status": "stored", "key": key}
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@app.post("/v3/memory/recall")
async def v3_memory_recall(request: Request):
    try:
        data = await request.json() if request.headers.get("content-type") == "application/json" else {}
        if isinstance(data, str):
            data = json.loads(data)
    except Exception:
        data = {}
    query = data.get("query", "").strip()
    if not query:
        return JSONResponse(content={"error": "query required", "results": []})
    try:
        from memory.database_memory import DatabaseMemory
        db = DatabaseMemory()
        results = db.search_facts(query, data.get("category"))
        return {"results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 55)
    logger.info("  JARVIS V3 FASTAPI (Render Edition)")
    logger.info("  Port: %s", PORT)
    logger.info("  Platform: Render Cloud")
    logger.info("  V3 Features: Planner | Tools | Verifier | Multi-LLM | Workflow | Memory")
    logger.info("  Agents: Coding | Image | Task | Research | Search | Reasoning | Chat | Goal")
    logger.info("  API Docs: http://0.0.0.0:%s/docs", PORT)
    logger.info("=" * 55)
    uvicorn.run("app_fastapi:app", host="0.0.0.0", port=PORT, reload=False)
