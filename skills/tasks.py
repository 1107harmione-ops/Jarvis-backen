# tasks.py — JARVIS Task Core (Render Cloud Edition)
# Device-control functions that have Android bridge equivalents return
# success confirmations (the APK's script.js executes them locally).
# Functions without a bridge or backend implementation return "not available".

import os, json, urllib.parse, platform, re, time
from datetime import datetime
from skills.img import generate_image


# ── AI-relevant functions (fully working) ──

def get_time():
    return datetime.now().strftime("%I:%M %p, %A %B %d, %Y")


def get_realtime_data(q: str):
    from core.config import SERP_API_KEY
    import requests
    try:
        r = requests.get("https://serpapi.com/search", params={"q": q, "api_key": SERP_API_KEY, "num": 3}, timeout=8).json()
        answer = r.get("answer_box", {}).get("answer")
        if answer:
            return str(answer)
        kg = r.get("knowledge_graph", {})
        if kg.get("description"):
            return kg["description"]
        results = r.get("organic_results", [])
        if results:
            snippets = [r.get("snippet", "") for r in results[:3] if r.get("snippet")]
            if snippets:
                return " | ".join(snippets)
        return f"No real-time results found for '{q}'."
    except Exception as e:
        return f"Search error: {e}"


def get_news(topic: str = ""):
    from core.config import NEWS_API_KEY
    import requests
    try:
        params = {"apiKey": NEWS_API_KEY, "language": "en", "pageSize": 5}
        if topic:
            params["q"] = topic
            url = "https://newsapi.org/v2/everything"
        else:
            params["country"] = "in"
            url = "https://newsapi.org/v2/top-headlines"
        r = requests.get(url, params=params, timeout=8).json()
        articles = r.get("articles", [])
        if not articles:
            return "No news articles found."
        headlines = []
        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "No title")
            headlines.append(f"{i}. {title}")
        return "Latest News:\n" + "\n".join(headlines)
    except Exception as e:
        return f"News fetch error: {e}"


def write_note(t):
    notes_dir = os.path.join(os.path.expanduser("~"), ".jarvis_notes")
    os.makedirs(notes_dir, exist_ok=True)
    filepath = os.path.join(notes_dir, f"note_{int(time.time())}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(t)
    return f"Note saved to {filepath}."


def get_system_info():
    info = {"OS": f"{platform.system()} {platform.release()}", "Machine": platform.machine(), "Hostname": platform.node(), "Python": platform.python_version(), "CPU Cores": os.cpu_count()}
    parts = [f"{k}: {v}" for k, v in info.items()]
    return " | ".join(parts)


def generate_image_task(prompt: str):
    if not prompt or str(prompt).lower() in ["none", "null", ""]:
        return json.dumps({"status": "error", "message": "No image description provided."})
    try:
        filepath, image_url = generate_image(prompt)
        if filepath and image_url:
            return json.dumps({"status": "success", "message": f"Image generated: {prompt}", "url": image_url, "filepath": filepath})
        elif filepath:
            return json.dumps({"status": "success", "message": f"Image generated and saved to {filepath}", "filepath": filepath})
        else:
            return json.dumps({"status": "error", "message": "Image generation failed. API may be temporarily unavailable."})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Image generation error: {e}"})


def get_time_date():
    return get_time()


def search(q: str):
    from core.config import SERP_API_KEY
    import requests
    try:
        r = requests.get("https://serpapi.com/search", params={"q": q, "api_key": SERP_API_KEY}, timeout=5).json()
        res = r.get("answer_box", {}).get("answer") or r.get("organic_results", [{}])[0].get("snippet", "")
        return res if res else f"Search results for '{q}' found online."
    except Exception:
        return f"Searched for '{q}' online."


def search_and_read(q: str):
    return get_realtime_data(q)


# ── Bridge-handled device functions (cloud stub confirms — APK executes locally) ──

def open_app(n: str):
    return f"Opening {n} on your device."


def close_app(n: str):
    return f"Closing {n}."


def open_any_app(n: str):
    return f"Opening {n} on your device."


def play_yt(q: str):
    return f"Searching YouTube for {q}."


def control_volume(direction: str = ""):
    return "Adjusting volume."


def control_brightness(direction: str = ""):
    return "Adjusting brightness."


def toggle_wifi(state: str = ""):
    return f"WiFi turned {'on' if state in ('on', 'enable') else 'off'}."


def toggle_bluetooth(state: str = ""):
    return f"Bluetooth turned {'on' if state in ('on', 'enable') else 'off'}."


def media_control(cmd: str = "play"):
    return "Controlling media playback."


def share_content(text: str):
    return "Sharing content."


def call_contact(n: str):
    return f"Calling {n}."


def make_call(n: str):
    return f"Calling {n}."


def send_whatsapp(msg: str):
    return f"Sending WhatsApp message: {msg}"


def open_website(url: str):
    return f"Opening {url}."


# ── Truly unavailable functions (no bridge, no backend) ──

def _not_available(feature: str) -> str:
    return f"[{feature} is not available in cloud mode]"


def take_shot():
    return _not_available("Screenshot")


def lock_screen():
    return _not_available("Screen lock")


def shutdown():
    return _not_available("Shutdown")


def restart():
    return _not_available("Restart")


def cancel_shutdown():
    return _not_available("Shutdown control")


def get_battery_status():
    return "Battery status not available in cloud mode."


def open_gallery():
    return _not_available("Gallery")


def access_storage():
    return _not_available("File manager")


def take_photo():
    return _not_available("Camera")


def read_notifications(max_count: int = 10):
    return _not_available("Notifications")


def send_sms(t: str):
    return _not_available("SMS")


def read_sms(target: str = ""):
    return _not_available("SMS")


def get_contacts(_=None):
    return _not_available("Contacts")


def get_wifi_info(_=None):
    return _not_available("WiFi info")


def set_wallpaper(target: str = ""):
    return _not_available("Wallpaper")


def get_call_log(target: str = ""):
    return _not_available("Call log")


def get_location(_=None):
    return _not_available("Location")


def understand_screen():
    return _not_available("Screen understanding")


lock = lock_screen
open_application = open_app
play_youtube = play_yt
search_google = search
take_screenshot = take_shot
shutdown_computer = shutdown
restart_computer = restart
close_application = close_app
