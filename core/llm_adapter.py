# llm_adapter.py — Multi-provider LLM adapter
import json
import os
import re
import requests

GROQ_API_BASE = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")

PROVIDER_HEADERS = {
    "api.anthropic.com": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    "generativelanguage.googleapis.com": lambda key: {"Content-Type": "application/json"},
}

def get_headers():
    base = GROQ_API_BASE.lower()
    for domain, header_fn in PROVIDER_HEADERS.items():
        if domain in base:
            return header_fn(GROQ_CHAT_API_KEY)
    return {"Authorization": f"Bearer {GROQ_CHAT_API_KEY}", "Content-Type": "application/json"}

def adapt_payload(messages, model=None, temperature=0.7, max_tokens=1024):
    base = GROQ_API_BASE.lower()
    model = model or GROQ_CHAT_MODEL
    if "anthropic.com" in base:
        system_msg = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                user_msgs.append(m)
        return {"model": model, "system": system_msg, "messages": user_msgs, "max_tokens": max_tokens, "temperature": temperature}
    if "generativelanguage.googleapis.com" in base:
        contents = [{"role": "user" if m["role"] in ("user", "system") else "model", "parts": [{"text": m["content"]}]} for m in messages]
        return {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
    return {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}

def adapt_response(response_json, base_url):
    base = base_url.lower()
    if "anthropic.com" in base:
        content = response_json.get("content", [{}])
        return content[0].get("text", "") if content else ""
    if "generativelanguage.googleapis.com" in base:
        candidates = response_json.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", [{}]) if candidates else [{}]
        return parts[0].get("text", "") if parts else ""
    choices = response_json.get("choices", [{}])
    message = choices[0].get("message", {})
    return message.get("content", "")

def llm_completion(messages, model=None, temperature=0.7, max_tokens=1024):
    if not GROQ_CHAT_API_KEY:
        return "[LLM not configured - set GROQ_CHAT_API_KEY in .env]"
    payload = adapt_payload(messages, model, temperature, max_tokens)
    headers = get_headers()
    base = GROQ_API_BASE.rstrip("/")
    if "generativelanguage.googleapis.com" in base:
        url = f"{base}/models/{GROQ_CHAT_MODEL}:generateContent?key={GROQ_CHAT_API_KEY}"
    elif "anthropic.com" in base:
        url = f"{base}/messages"
    else:
        url = f"{base}/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return adapt_response(r.json(), base)
    except requests.exceptions.Timeout:
        return "[LLM timeout - provider may be slow or unreachable]"
    except requests.exceptions.HTTPError as e:
        status = r.status_code if 'r' in dir() else '?'
        body = r.text[:500] if 'r' in dir() else ''
        return f"[LLM error {status}: {e}. Body: {body}]"
    except Exception as e:
        return f"[LLM error: {e}]"

def patch_groq_completion(module):
    if hasattr(module, "groq_completion"):
        module.groq_completion = llm_completion
        return True
    return False
