import os
from agents.base_agent import BaseAgent

class ImageAgent(BaseAgent):
    name = "ImageAgent"
    description = "Generates images from text descriptions using SeaArt AI"
    temperature = 0.4

    STYLES = {
        "realistic": "hyper realistic, 8k resolution, photorealistic, highly detailed",
        "anime": "anime art style, vibrant colors, Studio Ghibli inspired",
        "fantasy": "fantasy digital art, magical, ethereal lighting, dreamlike",
        "cyberpunk": "cyberpunk, neon lights, futuristic city, sci-fi",
        "portrait": "professional portrait, studio lighting, sharp focus",
        "watercolor": "watercolor painting, soft edges, artistic brush strokes",
        "sketch": "pencil sketch, black and white, hand drawn style",
        "logo": "clean logo design, minimal, professional, vector style",
    }

    ENHANCE_SYSTEM = """You are an expert image prompt engineer. 
Enhance the user's image description into a detailed, vivid prompt for an AI art generator.
Add: lighting, mood, style details, quality terms.
Keep it under 200 words. Return ONLY the enhanced prompt, nothing else."""

    def run(self, query: str, parameters: dict = None) -> dict:
        parameters = parameters or {}
        style = parameters.get("style", self._detect_style(query))
        enhanced = self._enhance_prompt(query, style)
        try:
            from skills.img import generate_image
            filepath, image_url = generate_image(enhanced, style=style)
        except Exception as e:
            return self._err(f"Image generation error: {e}")
        if not filepath and not image_url:
            return self._err("Image generation failed. The SeaArt API may be temporarily unavailable.")
        if filepath:
            result_text = "Image generated successfully!"
        else:
            result_text = "Image generated!"
        return self._ok(result_text, metadata={"task": "generate_image", "original_prompt": query, "enhanced_prompt": enhanced, "style": style, "filepath": filepath, "image_url": image_url})

    def _detect_style(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["anime", "cartoon", "manga"]): return "anime"
        if any(w in q for w in ["fantasy", "magic", "dragon", "wizard", "elf"]): return "fantasy"
        if any(w in q for w in ["cyber", "neon", "futuristic", "robot", "sci-fi"]): return "cyberpunk"
        if any(w in q for w in ["logo", "icon", "brand"]): return "logo"
        if any(w in q for w in ["portrait", "person", "face", "selfie"]): return "portrait"
        if any(w in q for w in ["sketch", "drawing", "pencil"]): return "sketch"
        if any(w in q for w in ["watercolor", "paint"]): return "watercolor"
        return "realistic"

    def _enhance_prompt(self, query: str, style: str) -> str:
        style_desc = self.STYLES.get(style, "")
        try:
            enhanced = self._ask([{"role": "user", "content": f"Enhance this image prompt: {query}\nStyle: {style_desc}"}], system=self.ENHANCE_SYSTEM, temperature=0.4, max_tokens=300)
            if enhanced and not enhanced.startswith("["):
                return enhanced
        except Exception:
            pass
        return f"{query}, {style_desc}"
