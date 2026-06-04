import os, sys, zipfile, json, time, threading, logging, io
from pathlib import Path

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = Path(__file__).parent / "vosk_model"
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_PATH = MODEL_DIR / MODEL_NAME

_log = logging.getLogger("vosk_stt")
_vosk_model = None
_model_lock = threading.Lock()


def _download_progress(url: str, dest: Path):
    import requests
    _log.info(f"Downloading Vosk model from {url} ...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = int(downloaded / total * 100)
                if pct % 10 == 0:
                    _log.info(f"  Vosk model download: {pct}%")
    _log.info("Vosk model download complete")


def _ensure_model():
    if MODEL_PATH.exists() and (MODEL_PATH / "am").exists():
        return MODEL_PATH
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MODEL_DIR / "model.zip"
    if not zip_path.exists():
        _download_progress(VOSK_MODEL_URL, zip_path)
    _log.info("Extracting Vosk model ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(MODEL_DIR)
    zip_path.unlink()
    _log.info(f"Vosk model ready at {MODEL_PATH}")
    return MODEL_PATH


def init_vosk():
    global _vosk_model
    with _model_lock:
        if _vosk_model is not None:
            return True
        try:
            model_path = _ensure_model()
            from vosk import Model
            _vosk_model = Model(str(model_path))
            _log.info("Vosk model loaded successfully")
            return True
        except Exception as e:
            _log.error(f"Failed to init Vosk: {e}")
            return False


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    if not audio_bytes:
        return ""
    if _vosk_model is None:
        if not init_vosk():
            return ""
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(_vosk_model, sample_rate)
    rec.SetWords(False)
    if isinstance(audio_bytes, bytes):
        rec.AcceptWaveform(audio_bytes)
    result = json.loads(rec.FinalResult())
    text = result.get("text", "").strip()
    return text


def transcribe_wav(wav_bytes: bytes) -> str:
    wav_bytes = _ensure_wav_format(wav_bytes)
    return transcribe(wav_bytes)


def _ensure_wav_format(data: bytes) -> bytes:
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return data
    import struct
    sample_rate = 16000
    channels = 1
    bits = 16
    data_size = len(data)
    header = io.BytesIO()
    header.write(b"RIFF")
    header.write(struct.pack("<I", 36 + data_size))
    header.write(b"WAVE")
    header.write(b"fmt ")
    header.write(struct.pack("<I", 16))
    header.write(struct.pack("<H", 1))
    header.write(struct.pack("<H", channels))
    header.write(struct.pack("<I", sample_rate))
    header.write(struct.pack("<I", sample_rate * channels * bits // 8))
    header.write(struct.pack("<H", channels * bits // 8))
    header.write(struct.pack("<H", bits))
    header.write(b"data")
    header.write(struct.pack("<I", data_size))
    header.write(data)
    return header.getvalue()


def is_available():
    return _vosk_model is not None


def get_model_info():
    return {"model": MODEL_NAME, "path": str(MODEL_PATH), "loaded": _vosk_model is not None}
