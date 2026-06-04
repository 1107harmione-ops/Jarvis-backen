import json
import os
import re
import time
import hashlib
from datetime import datetime

from core.config import GROQ_API_BASE, GROQ_CHAT_API_KEY, GROQ_CHAT_MODEL
from core.data_center import DataCenter

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_skills")
INDEX_FILE = os.path.join(SKILLS_DIR, "index.json")

_ANALYST_SYSTEM = """You are JARVIS Skill Analyst. Given a completed task, extract a reusable skill.

Return ONLY valid JSON:
{
  "name": "<short skill name, max 50 chars>",
  "description": "<what this skill does, 1-2 sentences>",
  "category": "<automation|research|coding|system|knowledge|general>",
  "trigger_phrases": ["<3-5 short phrases that should trigger this skill>"],
  "steps": ["<step 1>", "<step 2>", ...],
  "novelty": "high|medium|low"
}
"""


class SkillLibrary:
    def __init__(self):
        os.makedirs(SKILLS_DIR, exist_ok=True)
        self._index = self._load_index()
        self._datacenter = DataCenter()

    def _load_index(self):
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"skills": [], "last_learned": None}

    def _save_index(self):
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _skill_path(self, skill_id):
        return os.path.join(SKILLS_DIR, f"{skill_id}.json")

    def get_all(self):
        skills = []
        for info in self._index.get("skills", []):
            path = self._skill_path(info["id"])
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        skills.append(json.load(f))
                except Exception:
                    skills.append(info)
            else:
                skills.append(info)
        return skills

    def get_by_id(self, skill_id):
        path = self._skill_path(skill_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_relevant(self, query, limit=3):
        q = query.lower()
        scored = []
        for skill in self.get_all():
            score = 0
            for phrase in skill.get("trigger_phrases", []):
                if phrase.lower() in q:
                    score += 3
            for step in skill.get("steps", []):
                words = set(step.lower().split())
                q_words = set(q.split())
                overlap = len(words & q_words)
                if overlap > 0:
                    score += overlap * 0.5
            words_in = sum(1 for w in skill.get("description", "").lower().split() if w in q)
            score += words_in
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit]]

    def delete(self, skill_id):
        path = self._skill_path(skill_id)
        if os.path.exists(path):
            os.remove(path)
        self._index["skills"] = [s for s in self._index["skills"] if s["id"] != skill_id]
        self._save_index()
        return True

    def maybe_learn(self, query, response, agent, success, metadata=None):
        if not success:
            return None
        if agent == "chat":
            return None
        if not response or len(response) < 50:
            return None
        skill = self._analyze(query, response, agent, metadata)
        if not skill:
            return None
        if skill.get("novelty") == "low":
            return None
        if self._exists(skill["name"], skill["trigger_phrases"]):
            return None
        skill_id = self._generate_id(skill["name"])
        skill["id"] = skill_id
        skill["agent"] = agent
        skill["source_query"] = query[:200]
        skill["created_at"] = datetime.utcnow().isoformat(timespec="seconds")
        skill["updated_at"] = skill["created_at"]
        skill["usage_count"] = 0
        path = self._skill_path(skill_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(skill, f, indent=2, ensure_ascii=False)
        self._index["skills"].append({"id": skill_id, "name": skill["name"], "description": skill["description"], "category": skill.get("category", "general"), "created_at": skill["created_at"]})
        self._index["last_learned"] = skill["created_at"]
        self._save_index()
        self._datacenter.add_entry(topic=f"[Skill] {skill['name']}", summary=skill["description"], content=json.dumps(skill, indent=2), category="skill", tags=skill.get("trigger_phrases", []) + [skill.get("category", "general")], confidence=0.7)
        pass  # README update not applicable on Render
        print(f"[AutoSkill] Learned new skill: {skill['name']} ({skill_id})")
        return skill

    def _analyze(self, query, response, agent, metadata):
        prompt = (f"Task Query: {query}\nAgent Used: {agent}\nAgent Response: {response[:1500]}\n"
                  f"Metadata: {json.dumps(metadata or {})[:500]}\n\nExtract a reusable skill from this completed task.")
        try:
            import requests
            r = requests.post(f"{GROQ_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_CHAT_API_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_CHAT_MODEL, "messages": [
                    {"role": "system", "content": _ANALYST_SYSTEM},
                    {"role": "user", "content": prompt},
                ], "temperature": 0.3, "max_tokens": 500}, timeout=10)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    return json.loads(m.group())
        except Exception as e:
            print(f"[AutoSkill] Analysis failed: {e}")
        return None

    def _exists(self, name, phrases):
        name_lower = name.lower()
        for skill in self.get_all():
            if name_lower in skill.get("name", "").lower():
                return True
            overlap = len(set(phrases) & set(skill.get("trigger_phrases", [])))
            if overlap >= 2:
                return True
        return False

    def _generate_id(self, name):
        raw = f"{name}_{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _append_to_readme(self, skill):
        pass  # README update not applicable on Render
