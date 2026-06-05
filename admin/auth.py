import hashlib, time, os, threading, json
from functools import wraps
from flask import request, jsonify

ADMIN_PASSWORDS = {"codeten", "code10"}
TOKEN_EXPIRY = 1800
TOKEN_SECRET = os.environ.get("ADMIN_TOKEN_SECRET", "jarvis_admin_secret_change_me")
MAX_ATTEMPTS = 3
ATTEMPT_COOLDOWN = 30

_tokens = {}
_attempts = {}
_attempts_lock = threading.Lock()
_audit_log = []


def generate_token() -> str:
    raw = f"{time.time()}{os.urandom(16).hex()}{TOKEN_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_password(password: str) -> bool:
    return password.strip().lower() in ADMIN_PASSWORDS


def check_rate_limit(ip: str) -> tuple[bool, int]:
    with _attempts_lock:
        now = time.time()
        if ip in _attempts:
            entry = _attempts[ip]
            if now - entry["lock_until"] < 0:
                remaining = int(entry["lock_until"] - now)
                return False, remaining
            if now - entry["first_attempt"] > ATTEMPT_COOLDOWN:
                entry["count"] = 0
                entry["first_attempt"] = now
                entry["lock_until"] = 0
            entry["count"] += 1
            if entry["count"] >= MAX_ATTEMPTS:
                entry["lock_until"] = now + ATTEMPT_COOLDOWN
                return False, ATTEMPT_COOLDOWN
        else:
            _attempts[ip] = {"count": 1, "first_attempt": now, "lock_until": 0}
        return True, 0


def reset_attempts(ip: str):
    with _attempts_lock:
        _attempts.pop(ip, None)


def create_token() -> str:
    token = generate_token()
    _tokens[token] = time.time() + TOKEN_EXPIRY
    return token


def verify_token(token: str) -> bool:
    if token in _tokens:
        if time.time() < _tokens[token]:
            return True
        del _tokens[token]
    return False


def revoke_token(token: str):
    _tokens.pop(token, None)


def get_token_expiry(token: str) -> float:
    return _tokens.get(token, 0)


def clean_expired():
    now = time.time()
    for token, exp in list(_tokens.items()):
        if now >= exp:
            del _tokens[token]


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("X-Admin-Token", "")
        if not token or not verify_token(token):
            return jsonify({"error": "Unauthorized. Provide valid X-Admin-Token header.", "status": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


def log_audit(action: str, details: str = "", ip: str = ""):
    entry = {"timestamp": time.time(), "action": action, "details": details, "ip": ip}
    _audit_log.append(entry)
    if len(_audit_log) > 1000:
        _audit_log.pop(0)
    try:
        from db.mongo import mongo_db
        if mongo_db is not None:
            mongo_db.admin_audit.insert_one(entry)
    except Exception:
        pass


def get_audit_log(limit: int = 50) -> list:
    return list(reversed(_audit_log[-limit:]))


def cleanup_tokens():
    clean_expired()
    timer = threading.Timer(60, cleanup_tokens)
    timer.daemon = True
    timer.start()
