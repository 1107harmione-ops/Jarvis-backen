import os, sys, json, platform, time, subprocess, re
from pathlib import Path
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from admin.auth import verify_password, check_rate_limit, reset_attempts, create_token, verify_token, revoke_token, get_token_expiry, require_admin, log_audit, get_audit_log

admin_bp = Blueprint("admin", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent

_memory = None
_kb = None
_mongo = None

def init_admin(memory_instance=None, kb_instance=None, mongo_instance=None):
    global _memory, _kb, _mongo
    _memory = memory_instance
    _kb = kb_instance
    _mongo = mongo_instance


# ─── Auth ────────────────────────────────────────────────

@admin_bp.route("/admin/auth", methods=["POST"])
def auth():
    data = request.json or {}
    password = data.get("password", "")
    ip = request.remote_addr or "unknown"

    allowed, remaining = check_rate_limit(ip)
    if not allowed:
        log_audit("auth_rate_limited", f"IP: {ip}", ip)
        return jsonify({"status": "locked", "message": f"Too many attempts. Try again in {remaining}s.", "retry_after": remaining, "locked": True}), 429

    if not verify_password(password):
        log_audit("auth_failed", f"IP: {ip}", ip)
        return jsonify({"status": "denied", "message": "Invalid admin password.", "locked": False}), 401

    reset_attempts(ip)
    token = create_token()
    expiry = int(time.time()) + 1800
    log_audit("auth_granted", f"IP: {ip}", ip)
    return jsonify({"status": "granted", "token": token, "expires_at": expiry, "message": "Admin access granted. You have full system control."})


@admin_bp.route("/admin/verify", methods=["POST"])
def check_auth():
    token = request.headers.get("X-Admin-Token", "")
    if not token or not verify_token(token):
        return jsonify({"status": "invalid", "message": "Token expired or invalid."}), 401
    return jsonify({"status": "valid", "message": "Token is valid.", "expires_at": get_token_expiry(token) * 1000})


@admin_bp.route("/admin/logout", methods=["POST"])
def logout():
    token = request.headers.get("X-Admin-Token", "")
    if token:
        revoke_token(token)
        log_audit("logout", "Admin session ended", request.remote_addr)
    return jsonify({"status": "logged_out", "message": "Admin session closed."})


# ─── Files ───────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".py", ".txt", ".json", ".yaml", ".yml", ".html", ".js", ".css", ".md", ".kt", ".kts", ".xml", ".env", ".cfg", ".ini", ".conf", ".toml", ".sh", ".bat", ".csv", ".md"}

def _is_path_allowed(path: Path) -> bool:
    try:
        path = path.resolve()
        base = BASE_DIR.resolve()
        return str(path).startswith(str(base))
    except Exception:
        return False


@admin_bp.route("/admin/files", methods=["GET"])
@require_admin
def list_files():
    path_str = request.args.get("path", "/")
    target = (BASE_DIR / path_str.lstrip("/")).resolve()
    if not _is_path_allowed(target):
        return jsonify({"error": "Path outside project directory.", "entries": []}), 403
    if not target.exists():
        return jsonify({"error": "Path not found.", "entries": []}), 404
    if target.is_file():
        return jsonify({"error": "Path is a file, not a directory.", "entries": []}), 400
    try:
        entries = []
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            stat = entry.stat()
            entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(BASE_DIR)),
                "type": "dir" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else 0,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": entry.suffix if entry.is_file() else "",
            })
        return jsonify({"path": str(target.relative_to(BASE_DIR)), "entries": entries})
    except Exception as e:
        return jsonify({"error": str(e), "entries": []}), 500


@admin_bp.route("/admin/files/read", methods=["GET"])
@require_admin
def read_file():
    path_str = request.args.get("path", "")
    if not path_str:
        return jsonify({"error": "path parameter required"}), 400
    target = (BASE_DIR / path_str.lstrip("/")).resolve()
    if not _is_path_allowed(target):
        return jsonify({"error": "Path outside project directory."}), 403
    if not target.exists() or not target.is_file():
        return jsonify({"error": "File not found."}), 404
    try:
        content = target.read_text(encoding="utf-8")
        stat = target.stat()
        return jsonify({
            "path": str(target.relative_to(BASE_DIR)),
            "name": target.name,
            "extension": target.suffix,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "content": content,
        })
    except UnicodeDecodeError:
        return jsonify({"error": "Binary file cannot be read as text."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/admin/files/write", methods=["POST"])
@require_admin
def write_file():
    data = request.json or {}
    path_str = data.get("path", "")
    content = data.get("content", "")
    if not path_str:
        return jsonify({"error": "path required"}), 400
    target = (BASE_DIR / path_str.lstrip("/")).resolve()
    if not _is_path_allowed(target):
        return jsonify({"error": "Path outside project directory."}), 403
    ext = target.suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File extension '{ext}' not allowed for writing."}), 403
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log_audit("file_write", f"Wrote {target.relative_to(BASE_DIR)}", request.remote_addr)
        return jsonify({"status": "saved", "path": str(target.relative_to(BASE_DIR)), "size": len(content.encode("utf-8"))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Config ──────────────────────────────────────────────

CONFIG_MASKED_KEYS = {"GROQ_CHAT_API_KEY", "SERP_API_KEY", "NEWS_API_KEY"}
CONFIG_KEYS = [
    "GROQ_CHAT_API_KEY", "GROQ_CHAT_MODEL", "GROQ_CODING_MODEL",
    "GROQ_COMPOUND_MODEL", "SERP_API_KEY", "NEWS_API_KEY",
    "GROQ_API_BASE", "MONGO_URI",
]


@admin_bp.route("/admin/config", methods=["GET"])
@require_admin
def get_config():
    cfg = {}
    for key in CONFIG_KEYS:
        val = os.environ.get(key, "") or getattr(sys.modules.get("config"), key, "") if hasattr(sys.modules.get("config"), key) else os.environ.get(key, "")
        if key in CONFIG_MASKED_KEYS and val:
            val = val[:8] + "..." + val[-4:] if len(val) > 12 else "****"
        cfg[key] = val
    try:
        import config as cfg_module
        for key in dir(cfg_module):
            if not key.startswith("_") and key.isupper():
                if key not in cfg:
                    val = getattr(cfg_module, key)
                    if isinstance(val, (str, int, float, bool)):
                        cfg[key] = val
    except Exception:
        pass
    return jsonify({"config": cfg, "count": len(cfg)})


@admin_bp.route("/admin/config/update", methods=["POST"])
@require_admin
def update_config():
    data = request.json or {}
    key = data.get("key", "").strip().upper()
    value = data.get("value", "")
    if not key:
        return jsonify({"error": "key required"}), 400
    if key not in CONFIG_KEYS:
        return jsonify({"error": f"Unknown config key: {key}"}), 400
    os.environ[key] = value
    if key in CONFIG_MASKED_KEYS:
        log_audit("config_update", f"Updated {key} (masked)", request.remote_addr)
    else:
        log_audit("config_update", f"Updated {key} = {value}", request.remote_addr)
    return jsonify({"status": "updated", "key": key, "message": f"{key} updated. Restart may be required for some values."})


# ─── API Keys ────────────────────────────────────────────

PROVIDER_KEYS = {
    "groq": {"key_env": "GROQ_CHAT_API_KEY", "model_env": "GROQ_CHAT_MODEL"},
    "serp": {"key_env": "SERP_API_KEY"},
    "news": {"key_env": "NEWS_API_KEY"},
}


@admin_bp.route("/admin/api-keys", methods=["GET"])
@require_admin
def get_api_keys():
    keys = []
    for name, info in PROVIDER_KEYS.items():
        key_env = info.get("key_env", "")
        val = os.environ.get(key_env, "")
        masked = val[:8] + "..." + val[-4:] if len(val) > 12 else ("****" if val else "")
        entry = {"provider": name, "key_env": key_env, "key": masked, "has_key": bool(val)}
        if "model_env" in info:
            model = os.environ.get(info["model_env"], "")
            entry["model_env"] = info["model_env"]
            entry["model"] = model
        keys.append(entry)
    return jsonify({"keys": keys})


@admin_bp.route("/admin/api-keys/update", methods=["POST"])
@require_admin
def update_api_key():
    data = request.json or {}
    provider = data.get("provider", "").strip().lower()
    key_value = data.get("key", "").strip()
    model_value = data.get("model", "").strip()
    if provider not in PROVIDER_KEYS:
        return jsonify({"error": f"Unknown provider: {provider}. Valid: {', '.join(PROVIDER_KEYS.keys())}"}), 400
    info = PROVIDER_KEYS[provider]
    key_env = info.get("key_env", "")
    if key_value:
        os.environ[key_env] = key_value
        log_audit("api_key_update", f"Updated {provider} API key", request.remote_addr)
    if model_value and "model_env" in info:
        os.environ[info["model_env"]] = model_value
        log_audit("api_key_update", f"Updated {provider} model to {model_value}", request.remote_addr)
    return jsonify({"status": "updated", "provider": provider, "message": f"{provider} credentials updated."})


# ─── Providers (configurable list) ───────────────────────

@admin_bp.route("/admin/providers", methods=["GET"])
@require_admin
def get_providers():
    try:
        providers_file = BASE_DIR / "admin" / "providers.json"
        if providers_file.exists():
            data = json.loads(providers_file.read_text())
        else:
            data = _get_default_providers()
        return jsonify({"providers": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e), "providers": []}), 500


@admin_bp.route("/admin/providers/add", methods=["POST"])
@require_admin
def add_provider():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Provider name required"}), 400
    try:
        providers_file = BASE_DIR / "admin" / "providers.json"
        if providers_file.exists():
            providers = json.loads(providers_file.read_text())
        else:
            providers = _get_default_providers()
        if any(p.get("name", "").lower() == name.lower() for p in providers):
            return jsonify({"error": f"Provider '{name}' already exists"}), 409
        provider = {
            "name": name,
            "base_url": data.get("base_url", ""),
            "api_key_env": data.get("api_key_env", ""),
            "models": data.get("models", []),
            "enabled": data.get("enabled", True),
        }
        providers.append(provider)
        providers_file.write_text(json.dumps(providers, indent=2))
        log_audit("provider_add", f"Added provider: {name}", request.remote_addr)
        return jsonify({"status": "added", "provider": provider})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/admin/providers/remove", methods=["POST"])
@require_admin
def remove_provider():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Provider name required"}), 400
    try:
        providers_file = BASE_DIR / "admin" / "providers.json"
        if not providers_file.exists():
            return jsonify({"error": "No custom providers to remove"}), 404
        providers = json.loads(providers_file.read_text())
        filtered = [p for p in providers if p.get("name", "").lower() != name.lower()]
        if len(filtered) == len(providers):
            return jsonify({"error": f"Provider '{name}' not found"}), 404
        providers_file.write_text(json.dumps(filtered, indent=2))
        log_audit("provider_remove", f"Removed provider: {name}", request.remote_addr)
        return jsonify({"status": "removed", "provider": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/admin/providers/models/add", methods=["POST"])
@require_admin
def add_model():
    data = request.json or {}
    provider_name = data.get("provider", "").strip()
    model_name = data.get("model", "").strip()
    if not provider_name or not model_name:
        return jsonify({"error": "provider and model required"}), 400
    try:
        providers_file = BASE_DIR / "admin" / "providers.json"
        if not providers_file.exists():
            providers = _get_default_providers()
            providers_file.write_text(json.dumps(providers, indent=2))
        else:
            providers = json.loads(providers_file.read_text())
        for p in providers:
            if p.get("name", "").lower() == provider_name.lower():
                if model_name not in p.get("models", []):
                    p.setdefault("models", []).append(model_name)
                providers_file.write_text(json.dumps(providers, indent=2))
                log_audit("provider_model_add", f"Added model '{model_name}' to {provider_name}", request.remote_addr)
                return jsonify({"status": "added", "provider": provider_name, "model": model_name})
        return jsonify({"error": f"Provider '{provider_name}' not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/admin/providers/models/remove", methods=["POST"])
@require_admin
def remove_model():
    data = request.json or {}
    provider_name = data.get("provider", "").strip()
    model_name = data.get("model", "").strip()
    if not provider_name or not model_name:
        return jsonify({"error": "provider and model required"}), 400
    try:
        providers_file = BASE_DIR / "admin" / "providers.json"
        if not providers_file.exists():
            return jsonify({"error": "No custom providers"}), 404
        providers = json.loads(providers_file.read_text())
        for p in providers:
            if p.get("name", "").lower() == provider_name.lower():
                models = p.get("models", [])
                if model_name in models:
                    models.remove(model_name)
                providers_file.write_text(json.dumps(providers, indent=2))
                log_audit("provider_model_remove", f"Removed model '{model_name}' from {provider_name}", request.remote_addr)
                return jsonify({"status": "removed", "provider": provider_name, "model": model_name})
        return jsonify({"error": "Provider not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _get_default_providers():
    return [
        {"name": "groq", "base_url": "https://api.groq.com/openai/v1", "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"], "enabled": True},
        {"name": "openai", "base_url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-4o-mini"], "enabled": False},
    ]


# ─── Sessions ────────────────────────────────────────────

@admin_bp.route("/admin/sessions", methods=["GET"])
@require_admin
def list_sessions():
    if _memory is None:
        return jsonify({"error": "Memory module not available", "sessions": []}), 503
    limit = request.args.get("limit", 50, type=int)
    try:
        sessions = _memory.get_sessions(limit=limit)
        return jsonify({"sessions": sessions, "count": len(sessions)})
    except Exception as e:
        return jsonify({"error": str(e), "sessions": []}), 500


@admin_bp.route("/admin/sessions/<session_id>", methods=["GET"])
@require_admin
def view_session(session_id):
    if _memory is None:
        return jsonify({"error": "Memory module not available", "messages": []}), 503
    try:
        messages = _memory.get_session_messages(session_id)
        return jsonify({"session_id": session_id, "messages": messages, "count": len(messages)})
    except Exception as e:
        return jsonify({"error": str(e), "messages": []}), 500


@admin_bp.route("/admin/sessions/delete", methods=["POST"])
@require_admin
def delete_session():
    data = request.json or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if _memory is None:
        return jsonify({"error": "Memory module not available"}), 503
    try:
        _memory.delete_session(session_id)
        log_audit("session_delete", f"Deleted session: {session_id}", request.remote_addr)
        return jsonify({"status": "deleted", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Database ────────────────────────────────────────────

@admin_bp.route("/admin/db/query", methods=["POST"])
@require_admin
def db_query():
    data = request.json or {}
    collection = data.get("collection", "queries")
    query_filter = data.get("filter", {})
    limit = data.get("limit", 50)
    if _mongo is None:
        return jsonify({"error": "MongoDB not connected", "results": []}), 503
    try:
        col = _mongo[collection]
        results = list(col.find(query_filter).limit(limit).sort("timestamp", -1))
        for r in results:
            r["_id"] = str(r["_id"])
        return jsonify({"collection": collection, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e), "results": []}), 500


@admin_bp.route("/admin/db/stats", methods=["GET"])
@require_admin
def db_stats():
    stats = {"sqlite_knowledge": {}, "local_storage": {}}
    if _kb:
        try:
            stats["sqlite_knowledge"] = _kb.stats()
        except Exception as e:
            stats["sqlite_knowledge"]["error"] = str(e)
    if _memory:
        try:
            recent = _memory.get_recent_chat(1)
            stats["local_storage"]["chat_history"] = "available"
            stats["local_storage"]["recent_message"] = recent[0]["content"][:100] if recent else None
        except Exception as e:
            stats["local_storage"]["error"] = str(e)
    if _mongo is not None:
        try:
            mongo_stats = {}
            for name in _mongo.list_collection_names():
                mongo_stats[name] = _mongo[name].count_documents({})
            stats["mongodb"] = {"collections": mongo_stats, "connected": True}
        except Exception as e:
            stats["mongodb"] = {"connected": True, "error": str(e)}
    else:
        stats["mongodb"] = {"connected": False}
    return jsonify(stats)


# ─── System ──────────────────────────────────────────────

@admin_bp.route("/admin/system", methods=["GET"])
@require_admin
def system_info():
    info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "uptime": _get_uptime(),
        "cpu_count": os.cpu_count() or 0,
        "pid": os.getpid(),
        "project_root": str(BASE_DIR),
        "time": datetime.now(timezone.utc).isoformat(),
    }
    try:
        import psutil
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        info["memory"] = {"total": mem.total, "available": mem.available, "percent": mem.percent, "used": mem.used}
        disk = psutil.disk_usage("/")
        info["disk"] = {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent}
        boot_time = datetime.fromtimestamp(psutil.boot_time()).isoformat()
        info["boot_time"] = boot_time
    except ImportError:
        info["cpu_percent"] = "N/A (install psutil)"
        info["memory"] = "N/A"
        info["disk"] = "N/A"
        info["boot_time"] = "N/A"
    return jsonify(info)


@admin_bp.route("/admin/system/restart", methods=["POST"])
@require_admin
def restart_system():
    log_audit("system_restart", "App restart requested", request.remote_addr)
    threading = __import__("threading")
    threading.Thread(target=lambda: os._exit(0), daemon=True).start()
    return jsonify({"status": "restarting", "message": "Server is restarting..."})


@admin_bp.route("/admin/cache/clear", methods=["POST"])
@require_admin
def clear_cache():
    try:
        cache_file = BASE_DIR / "admin" / "providers.json"
        log_audit("cache_clear", "Response cache cleared", request.remote_addr)
        return jsonify({"status": "cleared", "message": "Cache cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Audit Log ───────────────────────────────────────────

@admin_bp.route("/admin/audit", methods=["GET"])
@require_admin
def audit_log():
    limit = request.args.get("limit", 50, type=int)
    logs = get_audit_log(limit=limit)
    return jsonify({"log": logs, "count": len(logs)})


# ─── Knowledge Base ──────────────────────────────────────

@admin_bp.route("/admin/knowledge", methods=["GET"])
@require_admin
def knowledge_list():
    if _kb is None:
        return jsonify({"error": "Knowledge base not available", "entries": []}), 503
    category = request.args.get("category")
    sort = request.args.get("sort", "recency")
    limit = request.args.get("limit", 50, type=int)
    try:
        entries = _kb.get_entries(category=category, sort=sort, limit=limit)
        return jsonify({"entries": entries, "count": len(entries)})
    except Exception as e:
        return jsonify({"error": str(e), "entries": []}), 500


@admin_bp.route("/admin/knowledge/<int:entry_id>", methods=["GET"])
@require_admin
def knowledge_entry(entry_id):
    if _kb is None:
        return jsonify({"error": "Knowledge base not available"}), 503
    try:
        entry = _kb.get_entry(entry_id)
        if not entry:
            return jsonify({"error": "Entry not found"}), 404
        return jsonify(entry)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Personality / Profile ───────────────────────────────

@admin_bp.route("/admin/personality", methods=["GET"])
@require_admin
def personality_profile():
    if _mongo is None:
        return jsonify({"error": "MongoDB not connected for personality data"}), 503
    try:
        user_id = request.args.get("user_id", "default")
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$agent", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]
        top_agents = list(_mongo.queries.aggregate(pipeline))
        total = _mongo.queries.count_documents({"user_id": user_id})
        recent = list(_mongo.queries.find({"user_id": user_id}).sort("timestamp", -1).limit(5))
        return jsonify({
            "user_id": user_id,
            "total_queries": total,
            "top_agents": [{"name": a["_id"], "count": a["count"]} for a in top_agents],
            "recent_queries": [{"query": r.get("query", ""), "agent": r.get("agent", ""), "time": r.get("timestamp", "")} for r in recent],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Helpers ─────────────────────────────────────────────

_start_time = time.time()

def _get_uptime():
    seconds = int(time.time() - _start_time)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)
