# JARVIS V3 — Archive of Old Backend Files

The following old files have been **superseded** by the new `backend/` package.
They are preserved here for reference during the transition.

## Superseded Files

| Old File | New Location | Status |
|----------|-------------|--------|
| `app.py` | `backend/main.py` | Replaced |
| `app_fastapi.py` | `backend/main.py` | Replaced |
| `config.py` | `backend/core/config.py` | Replaced |
| `admin/` | `backend/api/routes/admin.py` | Migrated |
| `agents/` | `backend/agents/` | Structurally same |
| `audio/voice.py` | `backend/voice/tts/engine.py` | Migrated |
| `core/` | `backend/core/` | Restructured |
| `memory/` | `backend/memory/manager.py` | Migrated |
| `speech/` | `backend/voice/stt/engine.py` | Migrated |
| `tools/` | `backend/tools/` | Restructured |
| `web/` | `backend/static/` | Moved |
| `Dockerfile` | `backend/deploy/Dockerfile` | Replaced |
| `requirements.txt` | `backend/requirements.txt` | Replaced |

## Migration Plan

1. **Phase 1**: ✅ New folder structure created
2. **Phase 2**: ✅ Core config, security, logging
3. **Phase 3**: ✅ JWT authentication
4. **Phase 4**: 🔲 Redis rate limiting (core/redis.py created, needs integration)
5. **Phase 5-6**: ✅ PostgreSQL + SQLAlchemy + Memory system
6. **Phase 7**: 🔲 Full Redis integration
7. **Phase 8**: ✅ WebSocket system
8. **Phase 9**: ✅ Tool system with sandbox (in progress)
9. **Phase 10**: 🔲 Android integration (FCM)
10. **Phase 11**: ✅ Observability (Loguru + OpenTelemetry)
11. **Phase 12**: ✅ Error handling
12. **Phase 13**: ✅ Pydantic Settings + .env
13. **Phase 14**: ✅ Deployment (Docker, Render, Railway, Alembic)
14. **Phase 15**: ✅ AI improvements (streaming, multi-agent)
15. **Phase 16**: ✅ MCP support (in progress)
16. **Phase 17**: ✅ Voice system
17. **Phase 18**: 🔲 Testing (in progress)
18. **Phase 19**: 🔲 Final security audit

## To Switch Production

Once testing is complete:

```bash
# 1. Update Render's start command to:
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT

# 2. Or use Docker:
cd backend && docker compose -f deploy/docker-compose.yml up -d

# 3. Run database migrations:
cd backend && alembic upgrade head
```

## Key Improvements

- ✅ **Authentication**: JWT + API keys + role-based access control
- ✅ **Database**: PostgreSQL with async SQLAlchemy + pgvector
- ✅ **Caching**: Redis for rate limiting, session storage, pub/sub
- ✅ **WebSockets**: Full duplex communication with auth
- ✅ **Streaming**: SSE for real-time LLM responses
- ✅ **Security**: Input sanitization, path traversal protection, HMAC signatures
- ✅ **Observability**: Structured logging (Loguru) + OpenTelemetry tracing
- ✅ **Error Handling**: Typed exceptions with proper HTTP status codes
- ✅ **Tool Sandbox**: Command whitelist, timeout, blocked patterns
- ✅ **MCP**: Model Context Protocol support for tool exposure
- ✅ **Deployment**: Docker, Render Blueprint, Railway config, Alembic migrations
- ✅ **Testing**: Async pytest fixtures, model tests, service tests
