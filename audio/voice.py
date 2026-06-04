import subprocess, os, sys, re, threading, requests
from typing import Optional, List

_speak_lock = threading.Lock()
_is_speaking = False

def is_speaking():
    return _is_speaking

IS_WINDOWS = sys.platform == "win32"
IS_TERMUX = "TERMUX_VERSION" in os.environ or os.path.isdir("/data/data/com.termux")

if IS_WINDOWS:
    import pyttsx3
else:
    pyttsx3 = None

if IS_WINDOWS:
    engine = None
    _engine_ready = False
else:
    engine = None

def _init_engine():
    global engine, _engine_ready
    if IS_WINDOWS and not engine:
        try:
            import pyttsx3
            engine = pyttsx3.init("sapi5")
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            voices = engine.getProperty("voices")
            if voices:
                for voice in voices:
                    if "Zira" in voice.name or "Female" in voice.name or "Hazel" in voice.name:
                        engine.setProperty("voice", voice.id)
                        break
            _engine_ready = True
        except Exception as e:
            print(f"[!] pyttsx3 Init Error: {e}")
            engine = None
            _engine_ready = False

def speak(text: str) -> None:
    global _is_speaking, engine
    try:
        clean_text = re.sub(r"https?://\S+|www\.\S+", "", text)
        clean_text = re.sub(r"[*_#`~]", "", clean_text)
        clean_text = re.sub(r"[!@$%^&()+{}\[\]:;<>\?~`\|\\/]", "", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        if not clean_text:
            return
        _is_speaking = True
        print(f"JARVIS: {clean_text}")
        if IS_WINDOWS:
            with _speak_lock:
                if not engine:
                    _init_engine()
                if engine:
                    try:
                        engine.say(clean_text)
                        engine.runAndWait()
                    except Exception as e:
                        print(f"[!] TTS Playback Error: {e}")
                        engine = None
        elif IS_TERMUX:
            subprocess.run(["termux-tts-speak", clean_text], capture_output=True)
        else:
            pass
    except Exception as e:
        print(f"[!] TTS Core Error: {e}")
    finally:
        _is_speaking = False

def listen_once(timeout: int = 30, phrase_time_limit: int = 30, language_list: Optional[List[str]] = None) -> str:
    print("Listening...")
    if IS_TERMUX:
        try:
            result = subprocess.run(["termux-speech-to-text"], capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return ""
    else:
        return input("Command: ").strip()

def listen_for_command(timeout: int = 30, phrase_time_limit: int = 30) -> str:
    return listen_once(timeout=timeout, phrase_time_limit=int(phrase_time_limit))

def bluetooth_mic_connected() -> bool:
    try:
        import subprocess, os
        try:
            p = subprocess.run(["pactl", "list", "sources"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1)
            if p.returncode == 0 and p.stdout:
                out = p.stdout.lower()
                if "bluez" in out or "bluetooth" in out:
                    return True
        except Exception:
            pass
        try:
            p = subprocess.run(["pactl", "list", "sinks"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1)
            if p.returncode == 0 and p.stdout:
                out = p.stdout.lower()
                if "bluetooth" in out or "bluez" in out:
                    return True
        except Exception:
            pass
        try:
            p = subprocess.run(["arecord", "-l"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1)
            if p.returncode == 0 and p.stdout:
                if "bluetooth" in p.stdout.lower():
                    return True
        except Exception:
            pass
        try:
            p = subprocess.run(["dumpsys", "bluetooth_manager"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1)
            if p.returncode == 0 and p.stdout and "connected" in p.stdout.lower():
                return True
        except Exception:
            pass
        if os.environ.get("BLUETOOTH_MIC_CONNECTED") in ("1", "true", "True"):
            return True
    except Exception:
        pass
    return False

_pipeline_instance = None

def get_voice_pipeline():
    global _pipeline_instance
    if _pipeline_instance is not None:
        return _pipeline_instance
    try:
        from core.config import USE_AUDIO_PIPELINE, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_FRAME_MS, ENERGY_THRESHOLD, VAD_AGGRESSIVENESS, SPEAKER_THRESHOLD, MAX_COMMAND_DURATION, SILENCE_TIMEOUT, SPEAKER_RECHECK_INTERVAL, SPEAKER_PROFILE_PATH, USE_OFFLINE_STT, WAKE_WORD, ENFORCE_SPEAKER_VERIFICATION
        if not USE_AUDIO_PIPELINE:
            return None
        from audio.audio_pipeline import VoicePipeline
        config = {"sample_rate": AUDIO_SAMPLE_RATE, "channels": AUDIO_CHANNELS, "frame_ms": AUDIO_FRAME_MS, "energy_threshold": ENERGY_THRESHOLD, "vad_aggressiveness": VAD_AGGRESSIVENESS, "speaker_threshold": SPEAKER_THRESHOLD, "max_command_duration": MAX_COMMAND_DURATION, "silence_timeout": SILENCE_TIMEOUT, "recheck_interval": SPEAKER_RECHECK_INTERVAL, "speaker_profile_path": SPEAKER_PROFILE_PATH, "enforce_speaker_verification": ENFORCE_SPEAKER_VERIFICATION, "use_offline_stt": USE_OFFLINE_STT, "wake_word": WAKE_WORD}
        _pipeline_instance = VoicePipeline(config=config)
        return _pipeline_instance
    except ImportError as e:
        print(f"[!] Audio pipeline not available: {e}")
        return None
    except Exception as e:
        print(f"[!] Audio pipeline init error: {e}")
        return None

def stop_voice_pipeline():
    global _pipeline_instance
    if _pipeline_instance and _pipeline_instance.is_running:
        _pipeline_instance.stop()
    _pipeline_instance = None
