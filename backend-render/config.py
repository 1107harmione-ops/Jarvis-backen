# config.py — JARVIS Backend Config (Render-compatible)
import os

PORT = int(os.environ.get("PORT", 8001))
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
GROQ_CODING_MODEL = os.environ.get("GROQ_CODING_MODEL", "llama-3.3-70b-versatile")
GROQ_COMPOUND_MODEL = os.environ.get("GROQ_COMPOUND_MODEL", "llama-3.3-70b-versatile")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
