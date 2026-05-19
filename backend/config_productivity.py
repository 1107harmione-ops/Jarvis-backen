# config_productivity.py — JARVIS Android Backend Config
import os

PORT = int(os.environ.get("PORT", 8001))
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
AUDIO_SAMPLE_RATE = 16000
SILENCE_TIMEOUT = 2.5
MAX_COMMAND_DURATION = 15
WAKE_WORD = "jarvis"
HOME = os.path.expanduser("~")
NOTES_DIR = os.environ.get("JARVIS_NOTES_DIR", os.path.join(HOME, "storage", "shared", "Jarvis_Notes"))
os.makedirs(NOTES_DIR, exist_ok=True)
TRAINING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "training_data")
os.makedirs(TRAINING_DIR, exist_ok=True)
