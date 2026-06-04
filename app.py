import sys, os, json, logging, time, re
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify
from config import PORT, GROQ_CHAT_API_KEY

app = Flask(__name__, template_folder="web", static_folder="web", static_url_path="/static")
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

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

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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

@app.route("/chat", methods=["POST"])
def chat_process():
    message = request.json.get("message", "").strip()
    if not message:
        return jsonify({"reply": "I didn't hear anything."})
    try:
        result = _orchestrator.run(message)
        response = result.get("response", "")
        agent_used = result.get("agent", "chat")
        metadata = result.get("metadata", {})
        time_ms = result.get("time_ms", 0)
        print(f"JARVIS (Render | {agent_used} | {time_ms}ms): {str(response)[:100]}")
        return jsonify({"reply": str(response), "agent": agent_used, "image_url": metadata.get("image_url"), "filepath": metadata.get("filepath"), "sources": metadata.get("sources"), "execution_output": metadata.get("execution_output"), "task": metadata.get("task"), "target": metadata.get("target"), "compound_execution": metadata.get("compound_execution"), "time_ms": time_ms, "training_entries": len(_training_knowledge), "training_sources": len(_training_sources), "status": "success" if result.get("success", True) else "error"})
    except Exception as e:
        print(f"Render Chat Error: {e}")
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

_vosk_ready = False
try:
    from speech.vosk_stt import init_vosk, get_model_info
    _vosk_ready = init_vosk()
    if _vosk_ready:
        print(f"[Vosk] STT ready: {get_model_info()['model']}")
    else:
        print("[Vosk] Not available (model download will retry on first request)")
except Exception as e:
    print(f"[Vosk] Init skipped: {e}")
    return jsonify({"status": "success", "training_entries": len(_training_knowledge), "training_sources": len(_training_sources)})

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
    token = (request.json or {}).get("token", "")
    if token != "jarvis_shutdown":
        return jsonify({"error": "invalid token"}), 403
    print("[JARVIS] Shutdown requested")
    os._exit(0)


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if not _vosk_ready:
        from speech.vosk_stt import init_vosk
        if not init_vosk():
            return jsonify({"error": "Vosk not available", "text": ""})
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided", "text": ""})
    file = request.files["audio"]
    audio_bytes = file.read()
    if not audio_bytes:
        return jsonify({"error": "Empty audio", "text": ""})
    try:
        from speech.vosk_stt import transcribe_wav
        text = transcribe_wav(audio_bytes)
        return jsonify({"text": text, "error": ""})
    except Exception as e:
        return jsonify({"error": str(e), "text": ""})


@app.route("/transcribe/json", methods=["POST"])
def transcribe_json():
    data = request.json or {}
    audio_b64 = data.get("audio", "")
    if not audio_b64:
        return jsonify({"error": "No audio data", "text": ""})
    import base64
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return jsonify({"error": "Invalid base64", "text": ""})
    if not _vosk_ready:
        from speech.vosk_stt import init_vosk
        if not init_vosk():
            return jsonify({"error": "Vosk not available", "text": ""})
    try:
        from speech.vosk_stt import transcribe_wav
        text = transcribe_wav(audio_bytes)
        return jsonify({"text": text, "error": ""})
    except Exception as e:
        return jsonify({"error": str(e), "text": ""})


@app.route("/transcribe/status", methods=["GET"])
def transcribe_status():
    from speech.vosk_stt import is_available, get_model_info
    return jsonify({"available": is_available(), "model": get_model_info()})


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
    print("\n" + "=" * 55)
    print("  JARVIS BACKEND (Render Edition)")
    print(f"  Port: {PORT}")
    print("  Platform: Render Cloud")
    print("  Agents: Coding | Image | Task | Research")
    print("           Search | Reasoning | Chat")
    print(f"  Training: {len(_training_knowledge)} entries")
    kb_stats = _kb.stats()
    print(f"  Knowledge: {kb_stats['total_entries']} entries, {len(kb_stats['entries_by_category'])} categories")
    print(f"  Vosk STT: {'ONLINE' if _vosk_ready else 'OFFLINE (auto-retry on request)'}")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
