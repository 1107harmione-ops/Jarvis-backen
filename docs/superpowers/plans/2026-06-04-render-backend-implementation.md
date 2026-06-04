# Render-Deployable Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a self-contained `backend-render/` directory from the original `backend/`, adapted for deployment on Render.com with all agents intact and Termux features gracefully degraded.

**Architecture:** Forked copy approach — `backend-render/` is a standalone copy of `backend/` with modifications to the Flask app (bind `0.0.0.0:$PORT`), device control functions (return "not available" stubs), and added Render deployment config (Gunicorn, render.yaml, Procfile).

**Tech Stack:** Python 3.11, Flask, Gunicorn, Groq/OpenAI-compatible LLM API, SerpAPI, NewsAPI

---

### Task 1: Create directory structure and base config

**Files:**
- Create: `backend-render/`
- Create: `backend-render/config.py`
- Create: `backend-render/runtime.txt`

- [ ] **Step 1: Create the backend-render directory and subdirectories**

```bash
cd /root/Jarvis-Ai-Assistant
mkdir -p backend-render/agents backend-render/core backend-render/skills backend-render/audio backend-render/web backend-render/auto_skills backend-render/training_data
```

- [ ] **Step 2: Write config.py**

Create `backend-render/config.py`:

```python
# config.py — JARVIS Backend Config (Render-compatible)
import os

PORT = int(os.environ.get("PORT", 8001))
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
```

- [ ] **Step 3: Write runtime.txt**

```bash
echo "python-3.11.9" > backend-render/runtime.txt
```

---

### Task 2: Copy core modules

**Files:**
- Create: `backend-render/core/__init__.py` (empty)
- Copy: `backend-render/core/personality.py` from `backend/core/personality.py`
- Copy: `backend-render/core/memory.py` from `backend/core/memory.py`
- Copy: `backend-render/core/brain.py` from `backend/core/brain.py`
- Copy: `backend-render/core/mini_gpt.py` from `backend/core/mini_gpt.py`
- Copy: `backend-render/core/llm_adapter.py` from `backend/core/llm_adapter.py`
- Copy: `backend-render/core/orchestrator.py` from `backend/core/orchestrator.py`
- Copy: `backend-render/core/data_center.py` from `backend/core/data_center.py`
- Copy: `backend-render/core/auto_skill.py` from `backend/core/auto_skill.py`
- Copy: `backend-render/core/config.py` from `backend-render/config.py` (we already wrote this)

- [ ] **Step 1: Copy all core files (unchanged)**

```bash
touch backend-render/core/__init__.py
cp backend/core/personality.py backend-render/core/personality.py
cp backend/core/memory.py backend-render/core/memory.py
cp backend/core/brain.py backend-render/core/brain.py
cp backend/core/mini_gpt.py backend-render/core/mini_gpt.py
cp backend/core/llm_adapter.py backend-render/core/llm_adapter.py
cp backend/core/orchestrator.py backend-render/core/orchestrator.py
cp backend/core/data_center.py backend-render/core/data_center.py
cp backend/core/auto_skill.py backend-render/core/auto_skill.py
```

- [ ] **Step 2: Fix the import path in data_center.py**

The original `data_center.py` imports `NOTES_DIR` from `core.config` and uses a Termux-specific path. It references `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` for `TRAINING_DIR`. The Render version should use a local directory instead. Modify the `TRAINING_DIR` and `NOTES_DIR` fallback in the copy:

Edit `backend-render/core/data_center.py`:

Replace:
```python
DEFAULT_DB = os.path.join(NOTES_DIR, "knowledge_store.db")
TRAINING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "training_data")
```

With:
```python
HOME = os.path.expanduser("~")
NOTES_DIR_RENDER = os.environ.get("JARVIS_NOTES_DIR", os.path.join(HOME, ".jarvis_data"))
os.makedirs(NOTES_DIR_RENDER, exist_ok=True)
DEFAULT_DB = os.path.join(NOTES_DIR_RENDER, "knowledge_store.db")
TRAINING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "training_data")
```

- [ ] **Step 3: Fix the import path in auto_skill.py and memory.py**

Edit `backend-render/core/memory.py`:

Replace:
```python
from core.config import NOTES_DIR
self.db_file = db_file or os.path.join(NOTES_DIR, "jarvis_memory.db")
```

With:
```python
import os
HOME = os.path.expanduser("~")
DATA_DIR = os.environ.get("JARVIS_NOTES_DIR", os.path.join(HOME, ".jarvis_data"))
os.makedirs(DATA_DIR, exist_ok=True)
self.db_file = db_file or os.path.join(DATA_DIR, "jarvis_memory.db")
```

Edit `backend-render/core/auto_skill.py`:

Replace:
```python
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_skills")
INDEX_FILE = os.path.join(SKILLS_DIR, "index.json")
README_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
```

With:
```python
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_skills")
INDEX_FILE = os.path.join(SKILLS_DIR, "index.json")
```

And remove the `_append_to_readme` method call in `maybe_learn`:

Replace:
```python
self._append_to_readme(skill)
```

With:
```python
pass  # README update not applicable on Render
```

You can also simplify by removing the `_append_to_readme` method if you want, but just commenting out the call is simplest.

---

### Task 3: Copy agent files

**Files:**
- Copy: `backend-render/agents/__init__.py` from `backend/agents/__init__.py`
- Copy: `backend-render/agents/base_agent.py` from `backend/agents/base_agent.py`
- Copy: `backend-render/agents/coding_agent.py` from `backend/agents/coding_agent.py`
- Copy: `backend-render/agents/image_agent.py` from `backend/agents/image_agent.py`
- Copy: `backend-render/agents/reasoning_agent.py` from `backend/agents/reasoning_agent.py`
- Copy: `backend-render/agents/research_agent.py` from `backend/agents/research_agent.py`
- Copy: `backend-render/agents/search_agent.py` from `backend/agents/search_agent.py`
- Copy: `backend-render/agents/task_agent.py` from `backend/agents/task_agent.py`

- [ ] **Step 1: Copy all agent files (unchanged)**

```bash
cp backend/agents/__init__.py backend-render/agents/__init__.py
cp backend/agents/base_agent.py backend-render/agents/base_agent.py
cp backend/agents/coding_agent.py backend-render/agents/coding_agent.py
cp backend/agents/image_agent.py backend-render/agents/image_agent.py
cp backend/agents/reasoning_agent.py backend-render/agents/reasoning_agent.py
cp backend/agents/research_agent.py backend-render/agents/research_agent.py
cp backend/agents/search_agent.py backend-render/agents/search_agent.py
cp backend/agents/task_agent.py backend-render/agents/task_agent.py
```

---

### Task 4: Write cloud-safe tasks.py

**Files:**
- Modify: `backend-render/skills/tasks.py` — all Termux device control functions return stubs
- Copy: `backend-render/skills/__init__.py` (empty)
- Copy: `backend-render/skills/img.py` (empty)

- [ ] **Step 1: Copy empty init files**

```bash
cp backend/skills/__init__.py backend-render/skills/__init__.py
cp backend/skills/img.py backend-render/skills/img.py
```

- [ ] **Step 2: Write cloud-safe tasks.py**

Create `backend-render/skills/tasks.py`:

```python
# tasks.py — JARVIS Task Core (Render Cloud Edition)
# All device-control functions return "not available" stubs.
# AI-relevant functions (get_time, get_news, get_realtime_data, etc.) work fully.

import os, json, webbrowser, urllib.parse, platform, re
from datetime import datetime
from skills.img import generate_image

def _not_available(feature: str) -> str:
    return f"[{feature} is not available in cloud mode]"

# ── AI-relevant functions (fully working) ──

def get_time():
    return datetime.now().strftime("%I:%M %p, %A %B %d, %Y")

def get_realtime_data(q: str):
    from core.config import SERP_API_KEY
    import requests
    try:
        r = requests.get("https://serpapi.com/search", params={"q": q, "api_key": SERP_API_KEY, "num": 3}, timeout=8).json()
        answer = r.get("answer_box", {}).get("answer")
        if answer:
            return str(answer)
        kg = r.get("knowledge_graph", {})
        if kg.get("description"):
            return kg["description"]
        results = r.get("organic_results", [])
        if results:
            snippets = [r.get("snippet", "") for r in results[:3] if r.get("snippet")]
            if snippets:
                return " | ".join(snippets)
        return f"No real-time results found for '{q}'."
    except Exception as e:
        return f"Search error: {e}"

def get_news(topic: str = ""):
    from core.config import NEWS_API_KEY
    import requests
    try:
        params = {"apiKey": NEWS_API_KEY, "language": "en", "pageSize": 5}
        if topic:
            params["q"] = topic
            url = "https://newsapi.org/v2/everything"
        else:
            params["country"] = "in"
            url = "https://newsapi.org/v2/top-headlines"
        r = requests.get(url, params=params, timeout=8).json()
        articles = r.get("articles", [])
        if not articles:
            return "No news articles found."
        headlines = []
        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "No title")
            headlines.append(f"{i}. {title}")
        return "Latest News:\n" + "\n".join(headlines)
    except Exception as e:
        return f"News fetch error: {e}"

def write_note(t):
    from core.config import PORT
    notes_dir = os.path.join(os.path.expanduser("~"), ".jarvis_notes")
    os.makedirs(notes_dir, exist_ok=True)
    filepath = os.path.join(notes_dir, f"note_{int(time.time())}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(t)
    return f"Note saved to {filepath}."

def get_system_info():
    info = {"OS": f"{platform.system()} {platform.release()}", "Machine": platform.machine(), "Hostname": platform.node(), "Python": platform.python_version(), "CPU Cores": os.cpu_count()}
    parts = [f"{k}: {v}" for k, v in info.items()]
    return " | ".join(parts)

def generate_image_task(prompt: str):
    if not prompt or str(prompt).lower() in ["none", "null", ""]:
        return json.dumps({"status": "error", "message": "No image description provided."})
    try:
        filepath, image_url = generate_image(prompt)
        if filepath and image_url:
            return json.dumps({"status": "success", "message": f"Image generated: {prompt}", "url": image_url, "filepath": filepath})
        elif filepath:
            return json.dumps({"status": "success", "message": f"Image generated and saved to {filepath}", "filepath": filepath})
        else:
            return json.dumps({"status": "error", "message": "Image generation failed. API may be temporarily unavailable."})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Image generation error: {e}"})

def get_time_date():
    return get_time()

# ── Device functions (stubs — not available in cloud) ──

def open_app(n: str):
    return _not_available("Open app")

def close_app(n: str):
    return _not_available("Close app")

def open_any_app(n: str):
    return _not_available("Open app")

def play_yt(q: str):
    return _not_available("YouTube playback")

def search(q: str):
    from core.config import SERP_API_KEY
    import requests
    try:
        r = requests.get("https://serpapi.com/search", params={"q": q, "api_key": SERP_API_KEY}, timeout=5).json()
        res = r.get("answer_box", {}).get("answer") or r.get("organic_results", [{}])[0].get("snippet", "")
        return res if res else f"Search results for '{q}' found online."
    except Exception:
        return f"Searched for '{q}' online."

def take_shot():
    return _not_available("Screenshot")

def lock_screen():
    return _not_available("Screen lock")

def shutdown():
    return _not_available("Shutdown")

def restart():
    return _not_available("Restart")

def cancel_shutdown():
    return _not_available("Shutdown control")

def get_battery_status():
    return "Battery status not available in cloud mode."

def control_volume(direction: str = ""):
    return _not_available("Volume control")

def control_brightness(direction: str = ""):
    return _not_available("Brightness control")

def toggle_wifi(state: str = ""):
    return _not_available("WiFi control")

def toggle_bluetooth(state: str = ""):
    return _not_available("Bluetooth control")

def open_website(url: str):
    return _not_available("Open website")

def open_gallery():
    return _not_available("Gallery")

def access_storage():
    return _not_available("File manager")

def take_photo():
    return _not_available("Camera")

def call_contact(n: str):
    return _not_available("Phone calls")

def read_notifications(max_count: int = 10):
    return _not_available("Notifications")

def send_sms(t: str):
    return _not_available("SMS")

def read_sms(target: str = ""):
    return _not_available("SMS")

def get_contacts(_=None):
    return _not_available("Contacts")

def media_control(cmd: str = "play"):
    return _not_available("Media control")

def share_content(text: str):
    return _not_available("Share")

def get_wifi_info(_=None):
    return _not_available("WiFi info")

def set_wallpaper(target: str = ""):
    return _not_available("Wallpaper")

def get_call_log(target: str = ""):
    return _not_available("Call log")

def get_location(_=None):
    return _not_available("Location")

def search_and_read(q: str):
    return get_realtime_data(q)

def understand_screen():
    return _not_available("Screen understanding")

lock = lock_screen
open_application = open_app
play_youtube = play_yt
search_google = search
take_screenshot = take_shot
shutdown_computer = shutdown
restart_computer = restart
close_application = close_app
```

---

### Task 5: Copy web UI and audio files

**Files:**
- Copy: all files from `backend/web/` to `backend-render/web/`
- Copy: `backend/audio/voice.py` to `backend-render/audio/voice.py`

- [ ] **Step 1: Copy web UI files**

```bash
cp backend/web/* backend-render/web/
```

- [ ] **Step 2: Copy audio module**

```bash
cp backend/audio/voice.py backend-render/audio/voice.py
```

---

### Task 6: Write the main Flask app (app.py)

**Files:**
- Create: `backend-render/app.py` (adapted from `backend/app_productivity.py`)

- [ ] **Step 1: Write app.py**

Create `backend-render/app.py`:

```python
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
        return jsonify({"reply": str(response), "agent": agent_used, "image_url": metadata.get("image_url"), "filepath": metadata.get("filepath"), "sources": metadata.get("sources"), "execution_output": metadata.get("execution_output"), "task": metadata.get("task"), "target": metadata.get("target"), "time_ms": time_ms, "training_entries": len(_training_knowledge), "training_sources": len(_training_sources), "status": "success" if result.get("success", True) else "error"})
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
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
```

---

### Task 7: Write Render deployment configuration files

**Files:**
- Create: `backend-render/requirements.txt`
- Create: `backend-render/Procfile`
- Create: `backend-render/render.yaml`
- Create: `backend-render/.env.example`

- [ ] **Step 1: Write requirements.txt**

```bash
cat > backend-render/requirements.txt << 'EOF'
flask>=3.0
requests>=2.31
numpy>=1.24
Pillow>=10.0
beautifulsoup4>=4.12
lxml>=5.0
groq>=0.5
gunicorn>=21.2
EOF
```

- [ ] **Step 2: Write Procfile**

```bash
echo "web: gunicorn app:app --bind 0.0.0.0:\$PORT --workers 1 --threads 4" > backend-render/Procfile
```

- [ ] **Step 3: Write render.yaml**

Create `backend-render/render.yaml`:

```yaml
services:
  - type: web
    name: jarvis-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4
    envVars:
      - key: GROQ_CHAT_API_KEY
        sync: false
      - key: SERP_API_KEY
        sync: false
      - key: NEWS_API_KEY
        sync: false
```

- [ ] **Step 4: Write .env.example**

Create `backend-render/.env.example`:

```bash
cat > backend-render/.env.example << 'EOF'
# Required: Get a free API key at https://console.groq.com
GROQ_CHAT_API_KEY=gsk_your_key_here

# Optional: SerpAPI key for web search (https://serpapi.com)
SERP_API_KEY=

# Optional: NewsAPI key for news (https://newsapi.org)
NEWS_API_KEY=
EOF
```

- [ ] **Step 5: Write .dockerignore (optional but helpful)**

```bash
cat > backend-render/.dockerignore << 'EOF'
.git
.gitignore
__pycache__
*.pyc
.env
.env.local
auto_skills/
training_data/
EOF
```

---

### Task 8: Verify the backend starts correctly

- [ ] **Step 1: Install dependencies**

```bash
cd /root/Jarvis-Ai-Assistant/backend-render
pip install -r requirements.txt 2>&1 | tail -5
```

- [ ] **Step 2: Test that imports work (without starting the full server)**

```bash
cd /root/Jarvis-Ai-Assistant/backend-render
python -c "
import sys
sys.path.insert(0, '.')
from config import PORT
print(f'Config OK, PORT={PORT}')
from core.orchestrator import Orchestrator
print('Orchestrator imported OK')
from agents import CodingAgent, ImageAgent, TaskAgent, ResearchAgent, SearchAgent, ReasoningAgent
print('All agents imported OK')
from core.data_center import DataCenter
print('DataCenter imported OK')
from core.memory import Memory
print('Memory imported OK')
print('All imports successful!')
"
```

- [ ] **Step 3: Start the server and verify health endpoint**

```bash
cd /root/Jarvis-Ai-Assistant/backend-render
PORT=9001 python app.py &
SERVER_PID=$!
sleep 2
curl -s http://127.0.0.1:9001/health
echo ""
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

Expected output: `{"status":"online","platform":"render","port":9001,...}`
