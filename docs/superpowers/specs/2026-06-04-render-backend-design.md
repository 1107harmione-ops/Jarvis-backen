# Render-Deployable Backend for Jarvis AI Assistant

## Goal
Create a standalone `backend-render/` directory — a copy of the original `backend/` adapted for deployment on Render.com, preserving all agents and functionality while gracefully degrading Termux/Android-specific device control features.

## Design Decisions

### Architecture
- **Forked copy** approach: `backend-render/` is a self-contained directory with all agents, core engine, and web UI duplicated from the original backend.
- Original `backend/` remains untouched for local Termux/Android usage.
- The Render backend can be developed and deployed independently.

### Key Adaptations

1. **Flask app** (`app.py`, was `app_productivity.py`):
   - Binds to `0.0.0.0` (Render requires this)
   - Uses `$PORT` environment variable (set by Render)
   - Removes Termux-only device endpoints (`/device/tts`, `/device/torch`, `/device/vibrate`, `/device/location`, `/device/sms`, `/device/notification`, `/device/clipboard`)
   - Keeps core AI endpoints: `/chat`, `/agent`, `/agents`, `/health`, `/status`, `/history`, `/knowledge/*`, `/auto-skills/*`
   - Serves web UI for testing via `/`

2. **Task agent degradation** (`skills/tasks.py`):
   - Device control functions return `"[Feature not available in cloud mode]"` instead of calling Termux commands
   - All AI-relevant functions (get_time, get_news, get_realtime_data, write_note, generate_image, search) work identically

3. **Production server**:
   - Gunicorn as WSGI server (Render standard)
   - `Procfile` entry: `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`
   - `render.yaml` for one-click Render deployment

4. **Environment variables** (set via Render dashboard):
   - `GROQ_CHAT_API_KEY` (required) — Groq API key
   - `SERP_API_KEY` (optional) — SerpAPI for search
   - `NEWS_API_KEY` (optional) — NewsAPI for news

### Directory Structure

```
backend-render/
├── app.py              # Main Flask app (0.0.0.0:$PORT)
├── config.py           # Render-safe config (no Termux paths)
├── requirements.txt    # + gunicorn
├── runtime.txt         # python-3.11.9
├── render.yaml         # Render deployment config
├── Procfile            # Gunicorn entry
├── agents/             # Copied from backend/agents/
│   ├── __init__.py
│   ├── base_agent.py
│   ├── chat_agent.py
│   ├── coding_agent.py
│   ├── image_agent.py
│   ├── reasoning_agent.py
│   ├── research_agent.py
│   ├── search_agent.py
│   └── task_agent.py
├── core/               # Copied from backend/core/
│   ├── __init__.py
│   ├── auto_skill.py
│   ├── brain.py
│   ├── config.py
│   ├── data_center.py
│   ├── llm_adapter.py
│   ├── memory.py
│   ├── mini_gpt.py
│   ├── orchestrator.py
│   └── personality.py
├── skills/             # Copied with modifications
│   ├── __init__.py
│   ├── img.py
│   └── tasks.py        # MODIFIED: cloud-safe device stubs
├── audio/
│   └── voice.py
└── web/                # Web UI for testing
    ├── index.html
    ├── script.js
    ├── style.css
    ├── knowledge.html
    ├── knowledge.css
    └── knowledge.js
```

### What Works on Render

| Feature | Status |
|---------|--------|
| Chat / LLM (Groq) | ✅ Fully functional |
| Web Search (SerpAPI) | ✅ Fully functional |
| Deep Research | ✅ Fully functional |
| Code Writing & Execution | ✅ Fully functional |
| Reasoning & Math | ✅ Fully functional |
| Image Generation | ✅ Fully functional |
| Knowledge Base | ✅ Fully functional |
| Auto-Skills Learning | ✅ Fully functional |
| Web UI (browser testing) | ✅ Functional |
| Device control (WiFi, BT, etc.) | ❌ Gracefully returns "not available" |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (for testing) |
| `/health` | GET | Health check |
| `/status` | GET | System status |
| `/chat` | POST | Process command (main endpoint) |
| `/agent` | POST | Direct agent call |
| `/agents` | GET | List agents |
| `/history` | GET | Chat history |
| `/knowledge/search` | POST | Knowledge base search |
| `/knowledge/stats` | GET | Knowledge base stats |
| `/auto-skills` | GET | List auto-skills |

### Render Deployment

1. Push `backend-render/` to a GitHub repo
2. On Render.com: New Web Service → connect repo
3. Set:
   - **Root Directory:** `backend-render`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`
4. Add environment variables:
   - `GROQ_CHAT_API_KEY`
   - `SERP_API_KEY` (optional)
   - `NEWS_API_KEY` (optional)

### APK Connection

APK `MainActivity.kt` points `BACKEND_URL` to the Render URL (e.g. `https://jarvis-backend.onrender.com`) instead of `http://127.0.0.1:8001`. Core chat/agent endpoints remain identical.
