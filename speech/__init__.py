"""
Speech module — lite (Google Web Speech API) STT with Vosk fallback.
"""
from speech.lite_stt import transcribe, transcribe_wav, is_available, get_model_info
