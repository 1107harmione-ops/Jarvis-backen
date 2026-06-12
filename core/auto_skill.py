import json
import os
import re
import time
import hashlib
import logging
import threading
from datetime import datetime

from core.provider_manager import llm_completion
from core.data_center import DataCenter

logger = logging.getLogger("auto_skill")

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
        self._lock = threading.Lock()

    def _load_index(self):
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"skills": [], "last_learned": None}

    def _save_index(self):
        """Atomically save the index to avoid corruption on crash."""
        tmp = INDEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)
        os.replace(tmp, INDEX_FILE)

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
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
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
        with self._lock:
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
        with self._lock:
            self._index["skills"].append({
                "id": skill_id,
                "name": skill["name"],
                "description": skill["description"],
                "category": skill.get("category", "general"),
                "created_at": skill["created_at"],
            })
            self._index["last_learned"] = skill["created_at"]
            self._save_index()
        try:
            self._datacenter.add_entry(
                topic=f"[Skill] {skill['name']}",
                summary=skill["description"],
                content=json.dumps(skill, indent=2),
                category="skill",
                tags=skill.get("trigger_phrases", []) + [skill.get("category", "general")],
                confidence=0.7,
            )
        except Exception as e:
            logger.warning("DataCenter entry failed: %s", e)
        logger.info("[AutoSkill] Learned new skill: %s (%s)", skill["name"], skill_id)
        return skill

    def _analyze(self, query, response, agent, metadata):
        prompt = (
            f"Task Query: {query}\nAgent Used: {agent}\n"
            f"Agent Response: {response[:1500]}\n"
            f"Metadata: {json.dumps(metadata or {})[:500]}\n\n"
            "Extract a reusable skill from this completed task."
        )
        try:
            raw = llm_completion(
                messages=[{"role": "user", "content": prompt}],
                system=_ANALYST_SYSTEM,
                temperature=0.3,
                max_tokens=500,
            )
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.warning("[AutoSkill] Analysis failed: %s", e)
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
