# JARVIS — AI Voice Assistant

Full-stack AI voice assistant with a **Flask backend** (deployed on Render) and an **Android APK** with a crystal orb voice UI.

![Crystal Orb UI](https://img.shields.io/badge/UI-Crystal%20Orb-00ffff)

---

## Features

### Voice-First Interface
- **Crystal Orb UI** — Tap the orb to speak, hear spoken responses, long-press to reveal text input
- **Wake Word** — Optional "Jarvis" wake word activation
- **Speech Recognition** — Android `SpeechRecognizer` with Bluetooth mic fallback
- **Text-to-Speech** — Google TTS engine with language detection
- **Transcript Overlay** — Shows what you said and what JARVIS replied

### Backend AI (Flask on Render)
- **Groq-Powered** — LLM chat via Groq API (LLaMA/Mixtral)
- **Voice Pipeline** — Audio transcription via `/transcribe` endpoint
- **Memory** — Auto-saved conversation sessions with recall
- **Knowledge Base** — Searchable data center with categories
- **Auto-Skills** — Learns reusable skill patterns from conversations
- **V3 Task Engine** — Goal management, tool registry, multi-LLM provider, verifier

### Android App Capabilities
- Voice input / text input
- Crystal orb animated UI (rotating rings, glow, particles)
- System tools: WiFi, Bluetooth, volume, brightness control
- Screen recording, camera, contacts, SMS, calendar, location
- Accessibility service for automation
- Boot receiver for auto-start

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (crystal orb) |
| `/chat` | POST | Send a message |
| `/agent` | POST | Direct agent dispatch |
| `/agents` | GET | List available agents |
| `/history` | GET | Chat history |
| `/status` | GET | System status & stats |
| `/health` | GET | Health check |
| `/transcribe` | POST | Transcribe audio (file) |
| `/transcribe/json` | POST | Transcribe audio (base64 JSON) |
| `/transcribe/status` | GET | Transcription engine status |
| `/memory/save` | POST | Save session checkpoint |
| `/sessions` | GET | List past sessions |
| `/sessions/<id>` | GET | Get session messages |
| `/sessions/<id>` | DELETE | Delete a session |
| `/knowledge/search` | POST | Search knowledge base |
| `/knowledge/stats` | GET | Knowledge base stats |
| `/knowledge/categories` | GET | Knowledge categories |
| `/knowledge/entry` | GET | Get knowledge entry |
| `/knowledge/random` | GET | Random knowledge entry |
| `/auto-skills` | GET | List auto-skills |
| `/auto-skills/search` | POST | Search auto-skills |
| `/auto-skills/<id>` | GET | Get skill detail |
| `/v3/plan` | POST | Generate a plan |
| `/v3/goal` | POST | Create a goal |
| `/v3/goal/run` | POST | Execute a goal |
| `/v3/goals` | GET | List goals |
| `/v3/goals/<id>` | GET | Get goal detail |
| `/v3/tools` | GET | List available tools |
| `/v3/tools/execute` | POST | Execute a tool |
| `/v3/provider/health` | GET | LLM provider health |
| `/v3/provider/stats` | GET | LLM provider stats |
| `/v3/verify` | POST | Verify output |
| `/v3/memory/stats` | GET | V3 memory stats |
| `/v3/memory/store` | POST | Store in V3 memory |
| `/v3/memory/recall` | POST | Recall from V3 memory |
| `/training/refresh` | POST | Refresh training data |
| `/shutdown` | POST | Shutdown backend |

---

## Deploy on Render

1. Fork/clone this repo and connect to [Render](https://render.com)
2. Set the following environment variables:

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `GROQ_CHAT_API_KEY` | Yes | Your Groq API key |
   | `JARVIS_SHUTDOWN_TOKEN` | No | Token to secure `/shutdown` |
   | `FASTER_WHISPER_MODEL` | No | Whisper model size (default: `base`) |

3. **Start command**: `gunicorn app:app`
4. Deploy — the API is available at `https://your-app.onrender.com`

---

## Android APK

Download **[`Jarvis-Assistant.apk`](./Jarvis-Assistant.apk)** from the repo root and install on your device.

### Build from Source

```bash
cd frontend
export ANDROID_HOME=/path/to/android-sdk
./gradlew assembleDebug
# APK at: frontend/app/build/outputs/apk/debug/app-debug.apk
```

**Key dependencies**: Compose BOM 2024.06, Kotlin 2.0.0, AGP 8.7.0, OkHttp, Gson

### Connect to Your Backend

The app connects to `wss://jarvis-backen-ouhz.onrender.com` by default. To change the server URL, edit `SettingsManager.kt`:

```kotlin
// app/src/main/java/com/jarvis/SettingsManager.kt
val DEFAULT_URL = "https://your-app.onrender.com"
```

---

## Project Structure

```
├── app.py                  # Flask backend entry point
├── config.py               # Configuration & env vars
├── core/                   # Backend engine
│   ├── orchestrator.py     # Chat orchestration
│   ├── memory.py           # Session memory
│   ├── data_center.py      # Knowledge base
│   ├── auto_skill.py       # Auto-skill learning
│   ├── provider_manager.py # Multi-LLM providers
│   ├── goal_manager.py     # V3 goal engine
│   └── tool_registry.py    # V3 tool system
├── web/                    # Web UI (crystal orb)
│   ├── index.html
│   └── style.css
├── frontend/               # Android APK
│   └── app/src/main/java/com/jarvis/
│       ├── MainActivity.kt
│       ├── ChatState.kt
│       ├── Theme.kt
│       ├── Navigation.kt
│       ├── WebSocketClient.kt
│       ├── TTSManager.kt
│       └── ... (providers, screens, services)
├── Jarvis-Assistant.apk    # Prebuilt APK
└── requirements.txt        # Python dependencies
```
