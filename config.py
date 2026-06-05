# config.py — JARVIS Backend Config (Render-compatible)
import os
from dotenv import load_dotenv

load_dotenv()  # .env file se variables load honge automatically

PORT = int(os.environ.get("PORT", 8001))
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
GROQ_CODING_MODEL = os.environ.get("GROQ_CODING_MODEL", "llama-3.3-70b-versatile")
GROQ_COMPOUND_MODEL = os.environ.get("GROQ_COMPOUND_MODEL", "llama-3.3-70b-versatile")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# ── Stability / Performance ──
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", 50))
SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", 3600))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
