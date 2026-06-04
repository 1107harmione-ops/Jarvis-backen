import os
import requests
import time
import sys
from datetime import datetime
import re
import json


def sanitize_folder_name(name):
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')[:50]


def generate_image(prompt, style="realistic"):
    if not prompt or str(prompt).lower() in ["none", "null", ""]:
        print("No image description provided.")
        return None, None

    style_prompts = {
        "realistic": "hyper realistic, 8k, detailed, photorealistic",
        "anime": "anime style, vibrant colors, studio ghibli inspired",
        "fantasy": "fantasy art, magical, ethereal, dreamlike",
        "cyberpunk": "cyberpunk, neon lights, futuristic, sci-fi",
        "watercolor": "watercolor painting, soft edges, artistic",
        "oil_painting": "oil painting, brush strokes, classical art"
    }

    enhanced_prompt = f"{prompt}, {style_prompts.get(style, style_prompts['realistic'])}"
    print(f"JARVIS Neural Imaging: \"{prompt}\"")

    import urllib.parse
    encoded_prompt = urllib.parse.quote(enhanced_prompt)
    seed = int(time.time())
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?seed={seed}&nologo=true&enhance=true"

    try:
        img_response = requests.get(image_url, timeout=45)

        if img_response.status_code != 200 or len(img_response.content) < 1000:
            print(f"\nGeneration failed: HTTP {img_response.status_code}")
            return None, None

        base_dir = os.path.join(os.path.expanduser("~"), ".jarvis_images")
        folder_name = sanitize_folder_name(prompt)
        target_dir = os.path.join(base_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(target_dir, f"{date_str}.jpg")

        with open(filepath, 'wb') as f:
            f.write(img_response.content)

        print(f"Image saved: {filepath}")
        return filepath, image_url

    except Exception as e:
        print(f"\nGeneration error: {e}")
        return None, None
