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
    return jsonify({"status": "online", "platform": "render", "port": PORT, "timestamp": datetime.now(timezone.utc).isoformat()})

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
    if not message:
        return jsonify({"reply": "I didn't hear anything."})
    try:
        result = _orchestrator.run(message)
        response = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        time_ms = result.get("time_ms", 0)
        logger.info("Chat | agent=%s | time=%dms | msg=%s", agent_used, time_ms, str(message)[:80])
        return jsonify({"reply": str(response), "agent": agent_used, "image_url": metadata.get("image_url"), "filepath": metadata.get("filepath"), "sources": metadata.get("sources"), "execution_output": metadata.get("execution_output"), "task": metadata.get("task"), "target": metadata.get("target"), "compound_execution": metadata.get("compound_execution"), "time_ms": time_ms, "training_entries": len(_training_knowledge), "training_sources": len(_training_sources), "status": "success" if result.get("success", True) else "error"})
    except Exception as e:
        logger.error("Chat error: %s", e)
        return jsonify({"error": str(e), "reply": "I encountered a neural link error."})

@app.route("/agent", methods=["POST"])
def agent_direct():
    data = request.json or {}
    message = data.get("message", "").strip()
    agent_name = data.get("agent", "").strip()
    if not message:
        return jsonify({"error": "message required"})
    try:
        if agent_name:
            from agents import CodingAgent, ImageAgent, TaskAgent, ResearchAgent, SearchAgent, ReasoningAgent
            agent_map = {"coding": CodingAgent, "image": ImageAgent, "task": TaskAgent, "research": ResearchAgent, "search": SearchAgent, "reasoning": ReasoningAgent}
            cls = agent_map.get(agent_name.lower())
            if cls:
                result = cls().run(message, data.get("parameters", {}))
                return jsonify({"reply": result.get("result", ""), "agent": result.get("agent"), "metadata": result.get("metadata", {}), "status": "success" if result.get("success") else "error"})
            return jsonify({"error": f"Unknown agent: {agent_name}"})
        else:
            result = _orchestrator.run(message)
            return jsonify({"reply": result.get("response", ""), "agent": result.get("agent"), "metadata": result.get("metadata", {}), "time_ms": result.get("time_ms", 0), "status": "success" if result.get("success") else "error"})
    except Exception as e:
        return jsonify({"error": str(e)})

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
    return jsonify({"status": "online", "platform": "render", "time": datetime.now().strftime("%I:%M %p, %A %B %d, %Y"), "system": system, "training_entries": len(_training_knowledge), "training_sources": len(_training_sources), "knowledge_entries": kb_stats["total_entries"], "knowledge_categories": len(kb_stats["entries_by_category"])})

@app.route("/training/refresh", methods=["POST"])
def refresh_training():
    global _training_knowledge, _training_sources
    _training_knowledge, _training_sources = load_training_data()
    return jsonify({"status": "success", "training_entries": len(_training_knowledge), "training_sources": len(_training_sources)})

# --- Speech Recognition (Lite / Vosk fallback) ---
_stt_mode = "lite"
try:
    from speech.lite_stt import transcribe_wav, transcribe, is_available, get_model_info
    _ = transcribe_wav
    _ = get_model_info
    logger.info("STT Lite (Google Web Speech API) — ready, no model download needed")
except Exception as e:
    logger.warning("STT Lite init failed: %s", e)
    _stt_mode = "none"
    transcribe_wav = None

# Vosk as optional fallback (no auto-download)
_vosk_ready = False
try:
    from speech.vosk_stt import init_vosk
    _vosk_ready = init_vosk()
    if _vosk_ready:
        logger.info("Vosk fallback offline STT available")
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
    os.kill(os.getpid(), signal.SIGTERM)


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
        if not text and _vosk_ready:
            from speech.vosk_stt import transcribe_wav as vosk_transcribe
            text = vosk_transcribe(audio_bytes)
        return jsonify({"text": text, "error": ""})
    except Exception as e:
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
        if not text and _vosk_ready:
            from speech.vosk_stt import transcribe_wav as vosk_transcribe
            text = vosk_transcribe(audio_bytes)
        return jsonify({"text": text, "error": ""})
    except Exception as e:
        return jsonify({"error": str(e), "text": ""})


@app.route("/transcribe/status", methods=["GET"])
def transcribe_status():
    from speech.lite_stt import is_available, get_model_info
    info = get_model_info()
    info["vosk_available"] = _vosk_ready
    return jsonify({"available": is_available(), "model": info})


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


if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  JARVIS BACKEND (Render Edition)")
    logger.info("  Port: %s", PORT)
    logger.info("  Platform: Render Cloud")
    logger.info("  Agents: Coding | Image | Task | Research | Search | Reasoning | Chat")
    logger.info("  Training: %d entries", len(_training_knowledge))
    kb_stats = _kb.stats()
    logger.info("  Knowledge: %d entries, %d categories", kb_stats["total_entries"], len(kb_stats["entries_by_category"]))
    stt_status = "LITE (Google Web Speech)"
    if _vosk_ready:
        stt_status += " + Vosk fallback"
    logger.info("  STT: %s", stt_status)
    logger.info("=" * 55)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
