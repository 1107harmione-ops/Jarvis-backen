# JARVIS V3 Backend — Understanding Guide

## Overview

JARVIS V3 is a production-grade **voice-enabled AI assistant backend** built with **FastAPI** (Python). It provides a REST API + WebSocket interface for chat, voice interaction, tool execution, and memory management. The architecture follows a modular, layered design with full async support, JWT authentication, LLM provider fallback chains, and deployment-ready configuration for Docker, Render, and Railway.

**Version:** 3.0.0  
**Python:** 3.11+ (async/await throughout)  
**Key Frameworks:** FastAPI, SQLAlchemy (async), Pydantic, Redis, WebSocket  
**LLM Providers:** Groq (primary), Gemini, OpenRouter, Local DeepSeek  

---

## Project Structure

```
backend-render/
├── backend/                     # ★ Main refactored backend package
│   ├── api/
│   │   ├── dependencies/        # FastAPI dependency injection
│   │   │   ├── auth.py          #   JWT auth dependency (get_current_user)
│   │   │   ├── database.py      #   DB session dependency (get_db)
│   │   │   └── rate_limit.py    #   Rate limiting (Redis-backed)
│   │   ├── middleware/
│   │   │   ├── cors.py          #   CORS configuration
│   │   │   ├── logging.py       #   Request/response logging middleware
│   │   │   └── security.py      #   Security headers middleware (HSTS, CSP, etc.)
│   │   └── routes/
│   │       ├── admin.py         #   Admin endpoints
│   │       ├── auth.py          #   Register, login, refresh, logout, me
│   │       ├── chat.py          #   Chat completion (POST + SSE streaming)
│   │       ├── conversations.py #   Conversation CRUD
│   │       ├── health.py        #   Health check endpoint
│   │       ├── tools.py         #   Tool execution endpoints
│   │       ├── users.py         #   User profile management
│   │       └── voice.py         #   STT (speech-to-text) & TTS (text-to-speech)
│   ├── core/
│   │   ├── config.py            #   Pydantic Settings (env-based configuration)
│   │   ├── errors.py            #   Custom exception classes & handlers
│   │   ├── logging.py           #   Loguru-based logging + OpenTelemetry
│   │   ├── redis.py             #   Redis client (rate limiting, caching)
│   │   └── security.py          #   JWT, bcrypt, HMAC, input sanitization
│   ├── database/
│   │   └── __init__.py          #   Async SQLAlchemy engine + session factory
│   │   └── alembic/             #   Database migrations (Alembic)
│   ├── mcp/
│   │   ├── routes.py            #   MCP HTTP routes (SSE for tool listing/calls)
│   │   ├── server.py            #   MCPServer — Model Context Protocol server
│   │   └── tools.py             #   MCPToolAdapter — registers built-in tools as MCP
│   ├── memory/
│   │   └── manager.py           #   MemoryManager — pgvector + keyword memory search
│   ├── models/                  #   SQLAlchemy ORM models
│   │   ├── audio_log.py         #   Audio processing log entries
│   │   ├── conversation.py      #   Chat conversations
│   │   ├── device.py            #   Registered devices
│   │   ├── goal.py              #   User goals/tasks
│   │   ├── memory_entry.py      #   Memory entries (with pgvector embedding column)
│   │   ├── message.py           #   Individual chat messages
│   │   └── user.py              #   User accounts
│   ├── schemas/                 #   Pydantic request/response models
│   │   ├── chat.py              #   ChatRequest, ChatResponse, StreamChunk
│   │   ├── conversation.py      #   Conversation CRUD schemas
│   │   ├── health.py            #   Health status schema
│   │   ├── memory.py            #   Memory store/search schemas
│   │   ├── tool.py              #   Tool execute/list schemas
│   │   ├── user.py              #   UserCreate, UserLogin, TokenResponse, etc.
│   │   ├── voice.py             #   STTResponse, TTSRequest, TTSResponse
│   │   └── websocket.py         #   WSMessage, MessageType enum
│   ├── services/
│   │   ├── auth.py              #   Authentication service layer
│   │   ├── chat.py              #   Chat orchestration service
│   │   ├── conversation.py      #   Conversation management service
│   │   ├── llm.py               #   ★ LLMService — provider chain w/ circuit breaker
│   │   └── user.py              #   User profile service
│   ├── tests/                   #   ★ 63 tests across 13 modules
│   │   ├── conftest.py          #   Pytest fixtures (test DB, HTTP client, auth headers)
│   │   ├── run_tests.py         #   Test runner entrypoint
│   │   ├── test_config.py       #   Settings validation tests
│   │   ├── test_health.py       #   Health endpoint tests
│   │   ├── test_logging.py      #   Logging configuration tests
│   │   ├── test_memory.py       #   Memory manager tests
│   │   ├── test_models.py       #   ORM model tests
│   │   ├── test_security.py     #   JWT, bcrypt, input validation tests
│   │   ├── test_services.py     #   Service layer tests
│   │   ├── test_tools.py        #   Tool registry & sandbox tests
│   │   ├── test_voice.py        #   STT/TTS engine tests
│   │   └── test_websocket.py    #   WebSocket connection manager tests
│   ├── tools/
│   │   ├── builtin.py           #   Built-in tool implementations
│   │   ├── loader.py            #   Tool loading/discovery
│   │   ├── registry.py          #   ToolRegistry — global tool registration
│   │   └── sandbox.py           #   SandboxedExecutor — restricted command execution
│   ├── voice/
│   │   ├── processor.py         #   VoiceProcessor — audio format conversion, slicing
│   │   ├── stt/
│   │   │   └── engine.py        #   ★ STTEngine — 3-tier fallback chain
│   │   └── tts/
│   │       └── engine.py        #   ★ TTSEngine — 3-tier fallback chain
│   ├── websocket/
│   │   ├── handler.py           #   WebSocket event handler (auth, messages, commands)
│   │   ├── manager.py           #   ConnectionManager — connection lifecycle & routing
│   │   └── protocol.py          #   WSMessage model & MessageType enum
│   ├── static/                  #   Static files served by FastAPI
│   ├── generated_audio/         #   TTS-generated audio files
│   └── main.py                  #   ★ Application entrypoint (FastAPI app factory)
├── agents/                      # Legacy AI agent implementations
├── app.py                       # Legacy Flask app
├── app_fastapi.py               # Legacy FastAPI entry
├── audio/                       # Legacy audio modules
├── config.py                    # Legacy configuration
├── core/                        # Legacy core modules
├── memory/                      # Legacy memory modules
├── providers/                   # Legacy LLM provider modules
├── skills/                      # Legacy skill modules
├── speech/                      # Legacy STT modules
├── tools/                       # Legacy tool modules
├── admin/                       # Legacy admin modules
├── Dockerfile                   # Multi-stage Docker build
├── docker-compose.yml           # Local Docker Compose setup
├── render.yaml                  # Render.com deployment config
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Project metadata
└── .env.example                 # Environment variable template
```

---

## Architecture Overview

### Layered Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Application                     │
│  (main.py → create_app() → lifespan startup/shutdown)    │
├──────────────────────────────────────────────────────────┤
│                     Middleware                            │
│  CORS → SecurityHeaders → RequestLogging → Exception     │
├──────────────────────────────────────────────────────────┤
│                   Route Layer (API)                       │
│  /health  /api/v1/auth  /api/v1/chat  /api/v1/voice      │
│  /api/v1/users  /api/v1/conversations  /api/v1/tools     │
│  /api/v1/admin  /mcp  /ws (WebSocket)                    │
├──────────────────────────────────────────────────────────┤
│                  Service Layer                            │
│  LLMService  AuthService  ChatService  UserService        │
│  ConversationService  MemoryManager                      │
├──────────────────────────────────────────────────────────┤
│                  Tool / MCP Layer                         │
│  ToolRegistry  SandboxedExecutor  MCPServer               │
├──────────────────────────────────────────────────────────┤
│              Voice Layer                                  │
│  STTEngine (whisper→lite→vosk)  TTSEngine (espeak→gTTS)  │
│  VoiceProcessor (format conversion, slicing)              │
├──────────────────────────────────────────────────────────┤
│              Data Layer                                   │
│  SQLAlchemy (async)  Redis  pgvector                     │
│  Models: User, Conversation, Message, MemoryEntry, ...    │
└──────────────────────────────────────────────────────────┘
```

### Request Flow (Chat)

```
Client → POST /api/v1/chat
  → CORS Middleware
  → SecurityMiddleware (headers)
  → LoggingMiddleware (request logging)
  → Auth Dependency (JWT token → current_user)
  → DB Dependency (async session)
  → Chat Route Handler
    → Save user message to DB
    → LLMService.complete()  (Groq → Gemini → OpenRouter)
    → Save assistant response to DB
    → Return ChatResponse
```

### WebSocket Flow

```
Client → ws://host/ws?token=xxx
  → WebSocket endpoint in main.py
  → handle_websocket()
    → ConnectionManager.connect() (register + metadata)
    → Send CONNECTED + AUTH_SUCCESS messages
    → Message loop:
      PING → PONG
      USER_MESSAGE → LLM call → stream chunks → BOT_REPLY
      COMMAND → command handler (/help, /ping)
      TYPING → relay to user
  → On disconnect → ConnectionManager.disconnect() (cleanup)
  → Heartbeat checker runs every 30s, cleans stale connections
```

---

## Key Modules in Detail

### 1. Configuration (`backend/core/config.py`)

- **`Settings` class** — Pydantic `BaseSettings` loaded from `.env` file
- Covers: server, database, Redis, JWT, 5 LLM providers, STT/TTS, rate limiting, WebSocket, MCP, monitoring (OpenTelemetry/Sentry), Android FCM, feature flags
- `get_settings()` — LRU-cached singleton
- `reload_settings()` — clears cache for testing
- Validators: CORS origins parsing, default secret warnings in production

### 2. Security (`backend/core/security.py`)

- **Password hashing** — bcrypt via `passlib` (requires `bcrypt<4.2`)
- **JWT tokens** — Access (30min) + Refresh (7 days) via `python-jose`
  - `create_access_token()` / `create_refresh_token()` / `decode_token()` / `verify_token()`
  - Payload includes: sub, exp, iat, role, scp (scopes), type
- **API key generation** — `jv_{secrets.token_urlsafe(32)}` with bcrypt hash
- **HMAC signatures** — `sign_payload()` / `verify_signature()` (SHA256)
- **Input validation** — `sanitize_input()`, `validate_device_id()`, `validate_filename()`
- **Rate limit keys** — `rate_limit_key_ip()` / `rate_limit_key_user()`

### 3. Database (`backend/database/__init__.py`)

- **Async SQLAlchemy** with `asyncpg` (PostgreSQL) or `aiosqlite` (testing)
- `init_db(database_url)` — creates engine + session factory, auto-creates tables in dev
- `close_db()` — graceful shutdown
- `get_session()` — FastAPI dependency with auto-commit/rollback
- Uses **pgvector** for embedding similarity search in memory manager

### 4. LLM Service (`backend/services/llm.py`)

- **Provider chain**: Groq (priority) → Gemini → OpenRouter
- **Circuit breaker** per provider — 3 failures → 60s cooldown
- Each provider extends `LLMProvider` base class with:
  - `_check_circuit()` / `_record_failure()` / `_record_success()`
- **LLMService** orchestrates fallback:
  - `complete()` — first successful provider wins
  - `complete_stream()` — SSE streaming via Groq
  - `get_stats()` — per-provider call/token/latency metrics
- Providers: Groq (OpenAI-compatible), Gemini (google.generativeai), OpenRouter (OpenAI-compatible)

### 5. Voice System

#### STT Engine (`backend/voice/stt/engine.py`)
- **3-tier fallback chain**: faster-whisper → Lite STT (Google Web Speech) → Vosk
- `_ensure_torch_lib_path()` — sets `LD_LIBRARY_PATH` for torch shared libs before importing faster-whisper
- Each tier wrapped in try/except; chain continues on failure
- Returns: `{text, confidence, provider, error}`

#### TTS Engine (`backend/voice/tts/engine.py`)
- **3-tier fallback chain**: espeak-ng → gTTS (Google Cloud) → pyttsx3
- Auto-detects available engines at runtime
- Saves WAV files to `generated_audio/` directory
- Returns: `{filename, filepath, duration_ms, format}`

#### Voice Processor (`backend/voice/processor.py`)
- `convert_to_wav()` — raw audio → WAV with resampling (via soundfile + numpy)
- `_basic_wav_convert()` — fallback without numpy
- `get_audio_duration()` — WAV duration in seconds
- `slice_audio()` — time-based slicing
- `get_audio_level()` — RMS audio level (0.0–1.0)

### 6. WebSocket System

#### ConnectionManager (`backend/websocket/manager.py`)
- Thread-safe (asyncio.Lock) connection tracking
- `connect()` / `disconnect()` — connection lifecycle
- `send_message()` / `send_to_user()` / `broadcast()` — message routing
- `heartbeat_check()` — periodic stale connection cleanup (configurable idle timeout)
- Per-connection metadata: connected_at, user_id, client_host, last_activity

#### Handler (`backend/websocket/handler.py`)
- Protocol: CONNECTED → (AUTH_SUCCESS) → message loop
- Message types: PING/PONG, USER_MESSAGE → STREAM_CHUNK → BOT_REPLY, TYPING, COMMAND
- Token-based authentication on connect

### 7. Tools & MCP

#### Tool System (`backend/tools/`)
- **ToolRegistry** — global tool registration with metadata (name, description, input_schema)
- **SandboxedExecutor** — restricted shell command execution:
  - Command whitelist (`ALLOWED_COMMANDS`: date, ls, python3, echo, etc.)
  - Blocked patterns (`..`, `;`, `|`, `&&`, `$()`, etc.)
  - Timeout (default 10s) + output cap (100 KB)
- **Built-in tools** — Python function tools
- **MCPToolAdapter** — registers built-in tools as MCP resources

#### MCP Server (`backend/mcp/server.py`)
- Implements Model Context Protocol for LLM tool discovery
- `register_tool()` / `register_resource()` — registration
- `call_tool()` — async execution with error handling
- `list_tools()` / `list_resources()` — introspection
- MCP routes expose SSE endpoints for tool listing and calling

### 8. Memory System (`backend/memory/manager.py`)

- **Three memory types**: episodic (conversation history), semantic (facts/knowledge), procedural (how-to)
- **Vector search** — pgvector `<=>` cosine similarity (sentence-transformers embeddings)
- **Keyword fallback** — ILIKE search when embedding unavailable
- **TTL support** — auto-expiring memories
- Methods: `store()`, `search()`, `recall_recent()`, `forget()`

### 9. ORM Models (`backend/models/`)

| Model | Table | Key Fields |
|---|---|---|
| `User` | `users` | id (UUID), username, email, hashed_password, role, preferences (JSONB) |
| `Conversation` | `conversations` | id, user_id (FK), title, is_archived |
| `Message` | `messages` | id, conversation_id (FK), role, content, token_count, metadata (JSONB) |
| `MemoryEntry` | `memory_entries` | id, user_id (FK), content, memory_type, importance, embedding (vector), expires_at |
| `Device` | `devices` | id, user_id (FK), device_id, platform, fcm_token |
| `Goal` | `goals` | id, user_id (FK), title, status, priority, deadline |
| `AudioLog` | `audio_logs` | id, user_id (FK), session_id, duration_ms, status |

### 10. API Routes

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/health` | GET | Health check + uptime | No |
| `/api/v1/auth/register` | POST | User registration | No |
| `/api/v1/auth/login` | POST | User login | No |
| `/api/v1/auth/refresh` | POST | Refresh JWT token | No |
| `/api/v1/auth/logout` | POST | Logout (placeholder) | Yes |
| `/api/v1/auth/me` | GET | Current user profile | Yes |
| `/api/v1/chat` | POST | Chat completion | Yes |
| `/api/v1/chat/stream` | POST | SSE streaming chat | Yes |
| `/api/v1/chat/history` | GET | List conversations | Yes |
| `/api/v1/chat/{id}` | GET/DELETE | Get/delete conversation | Yes |
| `/api/v1/users/{id}` | GET/PUT | User profile CRUD | Yes |
| `/api/v1/conversations` | GET/POST | Conversation CRUD | Yes |
| `/api/v1/voice/stt` | POST | Speech-to-text (file upload) | Optional |
| `/api/v1/voice/tts` | POST | Text-to-speech | Optional |
| `/api/v1/voice/audio/{file}` | GET | Serve audio file | No |
| `/api/v1/tools` | GET/POST | List/execute tools | Yes |
| `/api/v1/admin` | GET | Admin dashboard | Admin |
| `/mcp/sse` | GET | MCP SSE stream | No |
| `/ws` | WebSocket | Real-time messaging | Token param |
| `/` | GET | Root (service info) | No |
| `/docs` | GET | Swagger UI (dev only) | No |

### 11. API Dependencies (`backend/api/dependencies/`)

| Dependency | File | Purpose |
|---|---|---|
| `get_current_user` | `auth.py` | Extracts JWT → validates → returns User model |
| `get_current_user_optional` | `auth.py` | Like above but returns None if no/invalid token |
| `get_db` | `database.py` | Yields async SQLAlchemy session with auto-commit |
| `check_rate_limit` | `rate_limit.py` | Redis-backed rate limiting per IP/user |

### 12. Middleware (`backend/api/middleware/`)

| Middleware | File | Purpose |
|---|---|---|
| `setup_cors` | `cors.py` | Configurable CORS origins, methods, headers |
| `SecurityMiddleware` | `security.py` | Security headers (HSTS, CSP, X-Frame-Options, etc.) |
| `LoggingMiddleware` | `logging.py` | Per-request logging (method, path, status, duration) |

### 13. Monitoring & Observability

- **Loguru** — structured logging with rotation, format configurable (JSON/text)
- **OpenTelemetry** — optional OTLP exporter for traces/metrics
- **Sentry** — optional error tracking
- **Logging middleware** — per-request duration tracking
- **LLM call logging** — per-provider success/failure, latency, token counts
- **Security event logging** — auth failures, suspicious activity

### 14. Testing (`backend/tests/`)

- **63 tests** across 13 modules using pytest + pytest-asyncio
- **Test database**: SQLite via aiosqlite (no PostgreSQL needed)
- **Mock strategy**: `app.dependency_overrides[get_db]` for route tests
- **Fixtures**: `test_engine`, `test_session`, `client`, `auth_headers`, `admin_headers`
- **Coverage**: config, health, logging, memory, models, security, services, tools, voice, WebSocket
- **Run**: `python backend/tests/run_tests.py` or `pytest backend/tests/ -v`

---

## Deployment

### Docker
```bash
docker build -t jarvis-backend .
docker run -p 8001:8001 --env-file .env jarvis-backend
```

### Docker Compose
```bash
docker-compose up -d
```
Limits: 512MB RAM, 1 CPU (suitable for Render free tier).

### Render
`render.yaml` — ready-to-deploy config for Render Web Service.

### Environment Variables
Key settings (see `backend/core/config.py` for full list):
- `DATABASE_URL` — PostgreSQL async connection string
- `REDIS_URL` — Redis connection (optional, degrades gracefully)
- `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` — LLM providers
- `SECRET_KEY` / `JWT_SECRET` — security (change in production!)
- `ENVIRONMENT` — `development`, `staging`, or `production`

---

## LLM Provider Fallback Logic

```
User request
    ↓
GroqProvider.complete()
  → API key set?       No → return None (skip)
  → Circuit open?      Yes → return None (skip)
  → Call API
    → Success?         Yes → return result ✓
    → Failure?         record_failure() → return None
    ↓
GeminiProvider.complete()
  → (same pattern)
    ↓
OpenRouterProvider.complete()
  → (same pattern)
    ↓
Fallback → "All providers unavailable" error message
```

Circuit breaker: 3 consecutive failures → open for 60s → half-open on next attempt.

---

## STT Fallback Chain

```
User speaks (audio bytes)
    ↓
faster-whisper
  → Model loaded?      No → skip
  → Transcribe
    → Success?         Yes → return text ✓
    → Failure?         log error → continue
    ↓
Lite STT (Google Web Speech API)
  → speech_recognition installed?  No → skip
  → Transcribe
    → Success?         Yes → return text ✓
    → Failure?         log error → continue
    ↓
Vosk (offline)
  → Vosk model found?  No → skip
  → Transcribe
    → Success?         Yes → return text ✓
    → Failure?         log error → continue
    ↓
Return empty result + error messages
```

---

## TTS Fallback Chain

```
Text to speak
    ↓
espeak-ng (configured)
  → Binary found?      No → try espeak
  → Run command
    → Success?         Yes → return audio file ✓
    → Failure?         log error → continue
    ↓
gTTS (Google Cloud TTS)
  → gtts installed?    No → skip
  → Save to file
    → Success?         Yes → return audio file ✓
    → Failure?         log error → continue
    ↓
pyttsx3 (local)
  → pyttsx3 available? No → skip
  → Save to file
    → Success?         Yes → return audio file ✓
    → Failure?         log error → continue
    ↓
Return error: "All TTS engines failed"
```

---

## Key Design Decisions

1. **Singleton pattern for global instances** — STTEngine, TTSEngine, ConnectionManager, LLMService, MemoryManager, MCPServer — all accessed via `get_*()` functions with lazy initialization.

2. **Circuit breaker for LLM providers** — prevents cascading failures when an API is down. 3 failures → 60s cooldown → automatic recovery.

3. **Command whitelist sandbox** — no arbitrary shell execution. Only explicitly allowed commands with blocked patterns for injection prevention.

4. **pgvector for memory** — vector similarity search with automatic keyword fallback when embedding service unavailable.

5. **Configurable fallback chains** — STT and TTS engines use ordered fallback chains configurable via `.env`.

6. **Optional Redis** — rate limiting and caching; the app degrades gracefully when Redis is unavailable.

7. **Async throughout** — all I/O (DB, LLM calls, audio processing) uses asyncio for optimal concurrency.

8. **Layered exception handling** — each layer catches and wraps exceptions appropriately, with structured logging throughout.

---

## Dependencies

**Core:** fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy[asyncio], asyncpg, aiosqlite  
**Auth:** python-jose[cryptography], passlib[bcrypt], bcrypt==4.1.3  
**LLM:** openai, google-generativeai  
**Voice:** faster-whisper, ctranslate2, torch, speechrecognition, vosk, gtts, pyttsx3, soundfile, numpy, espeak-ng (system)  
**Memory:** pgvector, sentence-transformers  
**Infra:** redis[hiredis], alembic, opentelemetry-*, sentry-sdk  
**Test:** pytest, pytest-asyncio, httpx
