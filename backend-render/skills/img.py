import requests, os, time, json

def generate_image(prompt: str, style: str = "realistic") -> tuple:
    try:
        encoded = requests.utils.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed={int(time.time())}"
        resp = requests.get(image_url, timeout=30)
        if resp.status_code == 200:
            filename = f"img_{int(time.time())}.jpg"
            filepath = os.path.join(os.path.expanduser("~"), ".jarvis_images", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath, image_url
        return None, None
    except Exception:
        return None, None