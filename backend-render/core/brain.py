import requests, json, re
from core.config import GROQ_API_BASE, GROQ_CHAT_MODEL, GROQ_CHAT_API_KEY
from core.personality import SYSTEM_PROMPT
from core.memory import Memory

mem, session = Memory(), requests.Session()

def ask_llm(messages, model=GROQ_CHAT_MODEL, history=None):
    ctx = f"{SYSTEM_PROMPT}\nContext: {mem.get_facts()}"
    if history:
        ctx += f"\nRecent History: {history}"
    payload = {"model": model, "messages": [{"role":"system","content":ctx}] + messages, "temperature":0.3}
    try:
        r = session.post(f"{GROQ_API_BASE}/chat/completions",
                         headers={"Authorization":f"Bearer {GROQ_CHAT_API_KEY}"}, json=payload, timeout=10)
        return r.json()['choices'][0]['message']['content'].strip() if r.status_code==200 else ""
    except: return ""

def process(command):
    prompt = """Return ONLY JSON: {"action":"open_app|play_yt|search|note|chat|etc", "target":"...", "res":"reply", "sub":[{"k":"..","v":"..","t":".."}]}"""
    res = ask_llm([{"role":"user", "content":f"{prompt}\nInput: {command}"}])
    try:
        data = json.loads(re.search(r'\{.*\}', res, re.S).group())
        for f in data.get('sub', []):
            try:
                mem.learn_fact(f['k'], f['v'], f.get('t', 'personal'))
            except Exception:
                pass
        return data.get('conscious', data)
    except Exception:
        return {"action":"chat", "target":command, "res":res}

conscious_subconscious_process = process
