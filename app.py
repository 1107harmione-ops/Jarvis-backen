import sys, os, json, logging, time, re, signal
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("jarvis")

from flask import Flask, render_template, request, jsonify
from config import PORT, GROQ_CHAT_API_KEY
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── API Key Check ──
if not GROQ_CHAT_API_KEY:
    raise RuntimeError("GROQ_CHAT_API_KEY not set! Add it to environment.")

app = Flask(__name__, template_folder="web", static_folder="web", static_url_path="/static")
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

logging.getLogger("werkzeug").setLevel(logging.ERROR)

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

# V3 lazy inits
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
init_admin(memory_instance=_memory, kb_instance=_kb)
app.register_blueprint(admin_bp)
cleanup_tokens()

# ── CORS ──
ALLOWED_ORIGINS = [
    "capacitor://localhost",
    "http://localhost",
    "http://127.0.0.1",
    "http://10.0.2.2",
]

@app.after_request
def add_cors(resp):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
    else:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
    return resp


@app.route("/health")
def health():
    providers = {}
    try:
        providers = get_provider_manager().health_status()
    except Exception:
        providers = {}
    return jsonify({
        "status": "online",
        "platform": "render",
        "port": PORT,
        "version": "3.0",
        "providers": providers,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/knowledge")
def knowledge_page():
    return render_template("knowledge.html")


@limiter.limit("20 per minute")
@app.route("/chat", methods=["POST"])
def chat_process():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    session_id = str(data.get("session_id", "")).strip()
    if not message:
        return jsonify({"reply": "I didn't hear anything."})
    logger.info("Chat | session=%s | msg=%s", session_id or "(none)", message[:80])
    try:
        result = _orchestrator.run(message, session_id=session_id)
        response = result.get("response", "") or "I processed your request but have no specific response."
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        time_ms = result.get("time_ms", 0)
        logger.info("Chat | agent=%s | time=%dms | msg=%s", agent_used, time_ms, str(message)[:80])
        return jsonify({
            "reply": str(response),
            "session_id": session_id,
            "agent": agent_used,
            "image_url": metadata.get("image_url"),
            "filepath": metadata.get("filepath"),
            "sources": metadata.get("sources"),
            "execution_output": metadata.get("execution_output"),
            "task": metadata.get("task"),
            "target": metadata.get("target"),
            "compound_execution": metadata.get("compound_execution"),
            "time_ms": time_ms,
            "training_entries": len(_training_knowledge),
            "training_sources": len(_training_sources),
            "status": "success" if result.get("success", True) else "error"
        })
    except Exception as e:
        logger.error("Chat error: %s", e)
        return jsonify({"error": str(e), "reply": "I encountered a neural link error."})

@app.route("/chat/history", methods=["GET"])
def chat_history():
    session_id = request.args.get("session_id", "").strip()
    limit = min(int(request.args.get("limit", "30")), 100)
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    try:
        history = _memory.get_session_history(session_id, limit)
        return jsonify({"session_id": session_id, "messages": history, "count": len(history)})
    except Exception as e:
        logger.error("Chat history error: %s", e)
        return jsonify({"error": str(e), "messages": []})

@app.route("/chat/clear", methods=["POST"])
def chat_clear():
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    try:
        _memory.clear_session(session_id)
        return jsonify({"status": "cleared", "session_id": session_id})
    except Exception as e:
        logger.error("Chat clear error: %s", e)
        return jsonify({"error": str(e)})

@app.route("/agent", methods=["POST"])
def agent_direct():
    # Use silent=True so missing/invalid Content-Type doesn't raise an exception
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    agent_name = data.get("agent", "").strip()
    if not message:
        return jsonify({"error": "message required"}), 400
    try:
        if agent_name:
            from agents import CodingAgent, ImageAgent, TaskAgent, ResearchAgent, SearchAgent, ReasoningAgent
            agent_map = {"coding": CodingAgent, "image": ImageAgent, "task": TaskAgent, "research": ResearchAgent, "search": SearchAgent, "reasoning": ReasoningAgent}
            cls = agent_map.get(agent_name.lower())
            if cls:
                result = cls().run(message, data.get("parameters", {}))
                return jsonify({"reply": result.get("result", ""), "agent": result.get("agent"), "metadata": result.get("metadata", {}), "status": "success" if result.get("success") else "error"})
            return jsonify({"error": f"Unknown agent: {agent_name}"}), 400
        else:
            result = _orchestrator.run(message)
            return jsonify({"reply": result.get("response", ""), "agent": result.get("agent"), "metadata": result.get("metadata", {}), "time_ms": result.get("time_ms", 0), "status": "success" if result.get("success") else "error"})
    except Exception as e:
        logger.error("Agent direct error: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route("/agents", methods=["GET"])
def list_agents():
    return jsonify(_orchestrator.list_agents())

@app.route("/history", methods=["GET"])
def get_history():
    return jsonify(_memory.get_recent_chat(20))

@app.route("/status", methods=["GET"])
def get_stats():
    system = f"Python {sys.version.split()[0]} | Render Cloud"
    import platform
    try:
        system = f"Render Cloud | Python {platform.python_version()} | {platform.machine()}"
    except Exception:
        pass
    kb_stats = _kb.stats()
    return jsonify({
        "status": "online",
        "platform": "render",
        "version": "3.0",
        "time": datetime.now().strftime("%I:%M %p, %A %B %d, %Y"),
        "system": system,
        "training_entries": len(_training_knowledge),
        "training_sources": len(_training_sources),
        "knowledge_entries": kb_stats["total_entries"],
        "knowledge_categories": len(kb_stats["entries_by_category"])
    })

@app.route("/training/refresh", methods=["POST"])
def refresh_training():
    global _training_knowledge, _training_sources
    _training_knowledge, _training_sources = load_training_data()
    return jsonify({"status": "success", "training_entries": len(_training_knowledge), "training_sources": len(_training_sources)})

# --- Speech Recognition (faster-whisper > Lite > Vosk fallback) ---
_stt_mode = "none"
transcribe_wav = None  # primary STT function (assigned by whichever module wins)

# 1) faster-whisper — offline, best quality, lazy model load
try:
    from speech.faster_whisper_stt import (
        transcribe_wav as fw_transcribe_wav,
        is_available as fw_available,
        init_model as fw_init,
    )
    # Try immediate init — if model already cached it will be ready
    if fw_init():
        transcribe_wav = fw_transcribe_wav
        _stt_mode = "faster-whisper"
        logger.info("STT: faster-whisper loaded (offline)")
    else:
        logger.info("STT: faster-whisper model not cached — will lazy-load on first request")
        transcribe_wav = fw_transcribe_wav
        _stt_mode = "faster-whisper-lazy"
except ImportError:
    logger.info("STT: faster-whisper not installed, skipping")
except Exception as e:
    logger.warning("STT: faster-whisper init warning: %s", e)

# 2) Lite (Google Web Speech API) fallback — always ready, no disk footprint
try:
    from speech.lite_stt import transcribe_wav as lite_transcribe_wav
    if _stt_mode == "none":
        transcribe_wav = lite_transcribe_wav
        _stt_mode = "lite"
        logger.info("STT: Lite (Google Web Speech API)")
    else:
        # Keep faster-whisper as primary, but store lite for fallback
        _lite_transcribe_wav = lite_transcribe_wav
        logger.info("STT: Lite available as fallback")
except Exception as e:
    logger.warning("STT: Lite init failed: %s", e)

# 3) Vosk as optional fallback (no auto-download)
_vosk_ready = False
try:
    from speech.vosk_stt import init_vosk
    _vosk_ready = init_vosk()
    if _vosk_ready:
        logger.info("STT: Vosk fallback available")
except Exception:
    pass

@app.route("/knowledge/search", methods=["POST"])
def knowledge_search():
    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query required", "results": []})
    category = data.get("category")
    limit = data.get("limit", 10)
    results = _kb.search(query, category=category, limit=limit)
    return jsonify({"results": results, "total": len(results)})

@app.route("/knowledge/stats", methods=["GET"])
def knowledge_stats():
    return jsonify(_kb.stats())

@app.route("/knowledge/categories", methods=["GET"])
def knowledge_categories():
    return jsonify(_kb.get_categories())

@app.route("/knowledge/entry", methods=["GET"])
def knowledge_entry():
    entry_id = request.args.get("id")
    if not entry_id:
        return jsonify({"error": "id parameter required"})
    try:
        entry = _kb.get_entry(int(entry_id))
        if not entry:
            return jsonify({"error": "entry not found"})
        return jsonify(entry)
    except ValueError:
        return jsonify({"error": "invalid id"})

@app.route("/knowledge/random", methods=["GET"])
def knowledge_random():
    count = request.args.get("count", 3, type=int)
    count = max(1, min(count, 20))
    return jsonify({"results": _kb.random_entries(count=count)})

@app.route("/auto-skills", methods=["GET"])
def auto_skills_list():
    return jsonify({"skills": _skills.get_all(), "count": len(_skills.get_all())})

@app.route("/auto-skills/search", methods=["POST"])
def auto_skills_search():
    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"skills": [], "count": 0})
    return jsonify({"skills": _skills.get_relevant(query, limit=5)})

@app.route("/auto-skills/<skill_id>", methods=["GET"])
def auto_skills_get(skill_id):
    skill = _skills.get_by_id(skill_id)
    if not skill:
        return jsonify({"error": "skill not found"})
    return jsonify(skill)

@app.route("/shutdown", methods=["POST"])
def shutdown_backend():
    shutdown_token = os.environ.get("JARVIS_SHUTDOWN_TOKEN", "").strip()
    if not shutdown_token:
        return jsonify({"error": "shutdown disabled"}), 503
    token = (request.get_json(silent=True) or {}).get("token", "")
    if token != shutdown_token:
        return jsonify({"error": "invalid token"}), 403
    logger.info("Shutdown requested — terminating gracefully")
    # Return response BEFORE sending SIGTERM so the client receives it
    import threading
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return jsonify({"status": "shutting down"}), 202


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if transcribe_wav is None:
        return jsonify({"error": "STT not available on this server", "text": ""})
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided", "text": ""})
    file = request.files["audio"]
    audio_bytes = file.read()
    if not audio_bytes:
        return jsonify({"error": "Empty audio", "text": ""})
    try:
        text = transcribe_wav(audio_bytes)
        # Fallback chain: faster-whisper → lite → vosk
        if not text:
            # Use globals() — _lite_transcribe_wav is a module-level variable, not local
            if _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
                text = globals()["_lite_transcribe_wav"](audio_bytes)
            if not text and _vosk_ready:
                from speech.vosk_stt import transcribe_wav as vosk_fallback
                text = vosk_fallback(audio_bytes)
        return jsonify({"text": text or "", "error": ""})
    except Exception as e:
        logger.error("Transcribe error: %s", e)
        return jsonify({"error": str(e), "text": ""})


@app.route("/transcribe/json", methods=["POST"])
def transcribe_json():
    if transcribe_wav is None:
        return jsonify({"error": "STT not available on this server", "text": ""})
    data = request.json or {}
    audio_b64 = data.get("audio", "")
    if not audio_b64:
        return jsonify({"error": "No audio data", "text": ""})
    import base64
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return jsonify({"error": "Invalid base64", "text": ""})
    try:
        text = transcribe_wav(audio_bytes)
        if not text:
            if _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
                text = globals()["_lite_transcribe_wav"](audio_bytes)
            if not text and _vosk_ready:
                from speech.vosk_stt import transcribe_wav as vosk_fallback
                text = vosk_fallback(audio_bytes)
        return jsonify({"text": text or "", "error": ""})
    except Exception as e:
        logger.error("Transcribe JSON error: %s", e)
        return jsonify({"error": str(e), "text": ""})


@app.route("/transcribe/status", methods=["GET"])
def transcribe_status():
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
    return jsonify(info)


# ─── Voice Chat (Button-Triggered, No Wake Word) ─────────────────────────────
# Flow: User taps button → records until silence/button release
#       → client sends audio here → server transcribes → orchestrator → reply
# No wake word: recording only begins when user explicitly presses the button.
# ─────────────────────────────────────────────────────────────────────────────

def _do_transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio bytes with full fallback chain (faster-whisper → lite → vosk)."""
    if transcribe_wav is None:
        return ""
    try:
        text = transcribe_wav(audio_bytes)
        if not text and _stt_mode.startswith("faster-whisper") and "_lite_transcribe_wav" in globals():
            text = globals()["_lite_transcribe_wav"](audio_bytes)
        if not text and _vosk_ready:
            from speech.vosk_stt import transcribe_wav as vosk_fallback
            text = vosk_fallback(audio_bytes)
        return text or ""
    except Exception as e:
        logger.error("STT transcription error: %s", e)
        return ""


@app.route("/voice-chat", methods=["POST"])
@limiter.limit("30 per minute")
def voice_chat():
    """
    Button-triggered voice chat — multipart audio file upload.
    No wake word. Recording starts only when the user taps the button.
    """
    if transcribe_wav is None:
        return jsonify({
            "error": "Speech recognition not available on this server.",
            "transcript": "", "reply": ""
        }), 503

    if "file" not in request.files and "audio" not in request.files:
        return jsonify({
            "error": "No audio file provided.", "transcript": "", "reply": ""
        }), 400
        
    file = request.files.get("file") or request.files.get("audio")
    audio_bytes = file.read()
    if not audio_bytes:
        return jsonify({
            "error": "Empty audio file received.", "transcript": "", "reply": ""
        }), 400

    start = time.time()

    # Step 1: Transcribe
    try:
        transcript = _do_transcribe(audio_bytes)
    except Exception as e:
        logger.error("voice-chat transcribe error: %s", e)
        return jsonify({
            "error": f"Transcription failed: {e}", "transcript": "", "reply": ""
        }), 500

    if not transcript or not transcript.strip():
        return jsonify({
            "transcript": "",
            "reply": "I didn't catch that. Please tap the button and speak again.",
            "agent": "stt",
            "metadata": {},
            "time_ms": int((time.time() - start) * 1000),
            "status": "no_speech",
            "error": "",
        })

    logger.info("voice-chat | transcript=%s", transcript[:80])

    # Step 2: Process through orchestrator
    try:
        result = _orchestrator.run(transcript.strip())
        reply = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("voice-chat | agent=%s time=%dms", agent_used, elapsed_ms)
        return jsonify({
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
        })
    except Exception as e:
        logger.error("voice-chat orchestrator error: %s", e)
        return jsonify({
            "error": str(e),
            "transcript": transcript,
            "reply": "I encountered an error processing your request.",
        }), 500


@app.route("/voice-chat/json", methods=["POST"])
@limiter.limit("30 per minute")
def voice_chat_json():
    """
    Button-triggered voice chat — JSON body with base64-encoded audio.
    """
    if transcribe_wav is None:
        return jsonify({
            "error": "Speech recognition not available.", "transcript": "", "reply": ""
        }), 503

    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio", "").strip()
    session_id = data.get("session_id", "").strip()

    if not audio_b64:
        return jsonify({
            "error": "No audio provided. Send base64-encoded audio in the 'audio' field.",
            "transcript": "", "reply": ""
        }), 400

    import base64
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return jsonify({
            "error": "Invalid base64 audio data.", "transcript": "", "reply": ""
        }), 400

    if not audio_bytes:
        return jsonify({
            "error": "Empty audio after decoding.", "transcript": "", "reply": ""
        }), 400

    start = time.time()

    # Step 1: Transcribe
    try:
        transcript = _do_transcribe(audio_bytes)
    except Exception as e:
        logger.error("voice-chat/json transcribe error: %s", e)
        return jsonify({
            "error": f"Transcription failed: {e}", "transcript": "", "reply": ""
        }), 500

    if not transcript or not transcript.strip():
        return jsonify({
            "transcript": "",
            "reply": "I didn't catch that. Please tap the button and speak again.",
            "agent": "stt",
            "metadata": {},
            "time_ms": int((time.time() - start) * 1000),
            "status": "no_speech",
            "error": "",
        })

    logger.info("voice-chat/json | transcript=%s", transcript[:80])

    # Step 2: Process through orchestrator
    try:
        result = _orchestrator.run(transcript.strip(), session_id=session_id)
        reply = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("voice-chat/json | agent=%s time=%dms", agent_used, elapsed_ms)
        return jsonify({
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
        })
    except Exception as e:
        logger.error("voice-chat/json orchestrator error: %s", e)
        return jsonify({
            "error": str(e),
            "transcript": transcript,
            "reply": "I encountered an error processing your request.",
        }), 500


@app.route("/voice-chat/status", methods=["GET"])
def voice_chat_status():
    """Check if button-triggered voice chat is available on this server."""
    stt_ready = transcribe_wav is not None
    return jsonify({
        "available": stt_ready,
        "stt_mode": _stt_mode,
        "vosk_fallback": _vosk_ready,
        "wake_word_enabled": False,
        "mode": "button_triggered",
        "endpoints": {
            "file_upload": "POST /voice-chat       (multipart/form-data, field: file/audio)",
            "base64_json": "POST /voice-chat/json  (application/json,    field: audio)",
            "status":      "GET  /voice-chat/status",
        },
        "message": (
            "Ready. Tap button to start, speak, stop recording — reply returned instantly."
            if stt_ready else
            "STT engine not loaded. Check server logs."
        ),
    })


@app.route("/memory/save", methods=["POST"])
def memory_save():
    data = request.json or {}
    session_id = data.get("session_id", "")
    preview = data.get("preview", "")
    name = data.get("name", "")
    if session_id:
        _memory.create_session(session_id, name)
        _memory.update_session(session_id, preview=preview, count=0)
        return jsonify({"status": "saved", "session_id": session_id})
    return jsonify({"status": "ok"})

@app.route("/sessions", methods=["GET"])
def list_sessions():
    limit = request.args.get("limit", 20, type=int)
    sessions = _memory.get_sessions(limit=limit)
    return jsonify({"sessions": sessions})

@app.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    messages = _memory.get_session_messages(session_id)
    return jsonify({"messages": messages})

@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    _memory.delete_session(session_id)
    return jsonify({"status": "deleted"})


# ═══════════════════════════════════════════════════════════════════
# V3 API Routes
# ═══════════════════════════════════════════════════════════════════

# ─── Planner ───
@app.route("/v3/plan", methods=["POST"])
def v3_plan():
    """Decompose a goal into subtasks (planning only, no execution)."""
    data = request.json or {}
    goal = data.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "goal required", "tasks": []})
    try:
        tasks = _orchestrator.run_plan(goal, data.get("context"))
        return jsonify({"goal": goal, "tasks": tasks, "task_count": len(tasks)})
    except Exception as e:
        logger.error("V3 plan error: %s", e)
        return jsonify({"error": str(e), "tasks": []})

# ─── Goal / Workflow ───
@app.route("/v3/goal", methods=["POST"])
def v3_create_goal():
    """Create and execute an autonomous goal."""
    data = request.json or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "description required"})
    try:
        goal = _get_goal_manager().create_goal(description, data.get("context"))
        return jsonify({
            "goal_id": goal.id if hasattr(goal, "id") else goal.get("goal_id", ""),
            "description": description,
            "status": "created"
        })
    except Exception as e:
        logger.error("V3 create goal error: %s", e)
        return jsonify({"error": str(e)})

@app.route("/v3/goal/run", methods=["POST"])
def v3_run_goal():
    """Run an autonomous workflow."""
    data = request.json or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "description required"})
    try:
        result = _orchestrator.run_goal(description, data.get("context"))
        return jsonify(result)
    except Exception as e:
        logger.error("V3 run goal error: %s", e)
        return jsonify({"error": str(e)})

@app.route("/v3/goals", methods=["GET"])
def v3_list_goals():
    """List all goals."""
    try:
        status = request.args.get("status")
        limit = request.args.get("limit", 20, type=int)
        goals = _get_goal_manager().list_goals(status=status, limit=limit)
        return jsonify({"goals": goals, "count": len(goals)})
    except Exception as e:
        return jsonify({"error": str(e), "goals": []})

@app.route("/v3/goals/<goal_id>", methods=["GET"])
def v3_get_goal(goal_id):
    """Get goal details."""
    try:
        goal = _get_goal_manager().get_goal(goal_id)
        if not goal:
            return jsonify({"error": "goal not found"})
        return jsonify(goal)
    except Exception as e:
        return jsonify({"error": str(e)})

# ─── Tools ───
@app.route("/v3/tools", methods=["GET"])
def v3_list_tools():
    """List all available tools."""
    try:
        registry = _get_tool_registry()
        tools = registry.list_tools()
        return jsonify({"tools": tools, "count": len(tools)})
    except Exception as e:
        return jsonify({"error": str(e), "tools": []})

@app.route("/v3/tools/execute", methods=["POST"])
def v3_execute_tool():
    """Execute a specific tool."""
    data = request.json or {}
    tool = data.get("tool", "").strip()
    params = data.get("parameters", {})
    if not tool:
        return jsonify({"error": "tool name required"})
    try:
        result = _orchestrator.run_tool(tool, params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

# ─── Provider Health ───
@app.route("/v3/provider/health", methods=["GET"])
def v3_provider_health():
    """Get health status of all LLM providers."""
    try:
        health = _orchestrator.get_provider_health()
        return jsonify({"providers": health})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/v3/provider/stats", methods=["GET"])
def v3_provider_stats():
    """Get detailed stats for all LLM providers."""
    try:
        pm = get_provider_manager()
        stats = pm.get_provider_stats()
        return jsonify({"providers": stats})
    except Exception as e:
        return jsonify({"error": str(e)})

# ─── Verifier ───
@app.route("/v3/verify", methods=["POST"])
def v3_verify():
    """Verify a task execution result."""
    data = request.json or {}
    task = data.get("task", {})
    result = data.get("result", {})
    if not task:
        return jsonify({"error": "task required"})
    try:
        verification = _orchestrator.verify_result(task, result)
        return jsonify(verification)
    except Exception as e:
        return jsonify({"error": str(e)})

# ─── Memory V3 ───
@app.route("/v3/memory/stats", methods=["GET"])
def v3_memory_stats():
    """Get V3 memory system stats."""
    try:
        from memory.database_memory import DatabaseMemory
        from memory.vector_memory import VectorMemory
        db = DatabaseMemory()
        vec = VectorMemory()
        return jsonify({
            "database_memory": True,
            "vector_memory": {"count": vec.count()}
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/v3/memory/store", methods=["POST"])
def v3_memory_store():
    """Store a fact in long-term memory."""
    data = request.json or {}
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()
    if not key or not value:
        return jsonify({"error": "key and value required"})
    try:
        from memory.database_memory import DatabaseMemory
        db = DatabaseMemory()
        db.store_fact(key, value, data.get("category", "general"), data.get("importance", 1))
        return jsonify({"status": "stored", "key": key})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/v3/memory/recall", methods=["POST"])
def v3_memory_recall():
    """Recall facts from long-term memory."""
    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query required", "results": []})
    try:
        from memory.database_memory import DatabaseMemory
        db = DatabaseMemory()
        results = db.search_facts(query, data.get("category"))
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  JARVIS V3 BACKEND (Render Edition)")
    logger.info("  Port: %s", PORT)
    logger.info("  Platform: Render Cloud")
    logger.info("  V3 Features: Planner | Tools | Verifier | Multi-LLM | Workflow | Memory")
    logger.info("  Agents: Coding | Image | Task | Research | Search | Reasoning | Chat | Goal")
    logger.info("  Training: %d entries", len(_training_knowledge))
    kb_stats = _kb.stats()
    logger.info("  Knowledge: %d entries, %d categories", kb_stats["total_entries"], len(kb_stats["entries_by_category"]))
    stt_status = _stt_mode.upper()
    if _vosk_ready:
        stt_status += " + Vosk"
    logger.info("  STT: %s", stt_status)
    logger.info("=" * 55)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
