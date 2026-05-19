import json
import os
import re
import sqlite3
import time
from datetime import datetime

from core.config import NOTES_DIR

DEFAULT_DB = os.path.join(NOTES_DIR, "knowledge_store.db")
TRAINING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "training_data")


class DataCenter:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY,
                    topic TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    category_id INTEGER REFERENCES categories(id),
                    confidence REAL DEFAULT 0.5,
                    quality_score INTEGER DEFAULT 5,
                    source_count INTEGER DEFAULT 0,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY,
                    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
                    tag TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
                    url TEXT,
                    title TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_entry ON tags(entry_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
            try:
                conn.execute('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                        topic, summary, content,
                        content='entries',
                        content_rowid='rowid',
                        tokenize='porter unicode61'
                    )
                ''')
            except sqlite3.OperationalError:
                pass
            default_cats = [
                ("coding", "Code generation, debugging, programming knowledge"),
                ("history", "Historical events, civilizations, figures"),
                ("agi", "Artificial General Intelligence theory and architectures"),
                ("technology", "Technology concepts, tools, frameworks"),
                ("human_nature", "Human behavior, psychology, neuroscience"),
                ("medical", "Medical knowledge, human body, diagnostics"),
                ("general", "General knowledge and miscellaneous topics"),
            ]
            for name, desc in default_cats:
                conn.execute("INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)", (name, desc))
            conn.commit()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def add_entry(self, topic, summary="", content="", category=None, tags=None, sources=None, confidence=0.5, quality_score=5):
        if not topic or not topic.strip():
            raise ValueError("topic is required")
        with self._conn() as conn:
            cat_id = None
            if category:
                row = conn.execute("SELECT id FROM categories WHERE name = ?", (category,)).fetchone()
                if row:
                    cat_id = row[0]
                else:
                    conn.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (category, f"Auto-created category: {category}"))
                    cat_id = conn.execute("SELECT id FROM categories WHERE name = ?", (category,)).fetchone()[0]
            source_list = sources or []
            cursor = conn.execute(
                "INSERT INTO entries (topic, summary, content, category_id, confidence, quality_score, source_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (topic.strip(), summary.strip(), content.strip(), cat_id, confidence, quality_score, len(source_list)),
            )
            entry_id = cursor.lastrowid
            for tag in (tags or []):
                tag = tag.strip().lower()[:50]
                if tag:
                    conn.execute("INSERT INTO tags (entry_id, tag) VALUES (?, ?)", (entry_id, tag))
            for src in source_list:
                url = src.get("url", "") if isinstance(src, dict) else src
                title = src.get("title", "") if isinstance(src, dict) else ""
                conn.execute("INSERT INTO sources (entry_id, url, title) VALUES (?, ?, ?)", (entry_id, url, title))
            try:
                conn.execute("INSERT INTO entries_fts (rowid, topic, summary, content) VALUES (?, ?, ?, ?)", (entry_id, topic.strip(), summary.strip(), content.strip()))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return entry_id

    def get_entry(self, entry_id):
        with self._conn() as conn:
            row = conn.execute("""
                SELECT e.id, e.topic, e.summary, e.content, c.name as category,
                       e.confidence, e.quality_score, e.source_count, e.access_count,
                       e.created_at, e.updated_at
                FROM entries e LEFT JOIN categories c ON e.category_id = c.id
                WHERE e.id = ?""", (entry_id,)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE entries SET access_count = access_count + 1 WHERE id = ?", (entry_id,))
            conn.commit()
            tags = [r[0] for r in conn.execute("SELECT tag FROM tags WHERE entry_id = ?", (entry_id,)).fetchall()]
            sources = [{"url": r[0], "title": r[1]} for r in conn.execute("SELECT url, title FROM sources WHERE entry_id = ?", (entry_id,)).fetchall() if r[0]]
            return {"id": row[0], "topic": row[1], "summary": row[2], "content": row[3],
                    "category": row[4], "confidence": row[5], "quality_score": row[6],
                    "source_count": row[7], "access_count": row[8] + 1,
                    "created_at": row[9], "updated_at": row[10],
                    "tags": tags, "sources": sources}

    def update_entry(self, entry_id, **kwargs):
        allowed = {"topic", "summary", "content", "confidence", "quality_score"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]
        with self._conn() as conn:
            conn.execute(f"UPDATE entries SET {set_clause} WHERE id = ?", values)
            if "topic" in updates or "summary" in updates or "content" in updates:
                row = conn.execute("SELECT topic, summary, content FROM entries WHERE id = ?", (entry_id,)).fetchone()
                if row:
                    try:
                        conn.execute("UPDATE entries_fts SET topic=?, summary=?, content=? WHERE rowid=?", (row[0], row[1], row[2], entry_id))
                    except sqlite3.OperationalError:
                        pass
            conn.commit()
        return True

    def delete_entry(self, entry_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM tags WHERE entry_id = ?", (entry_id,))
            conn.execute("DELETE FROM sources WHERE entry_id = ?", (entry_id,))
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            try:
                conn.execute("DELETE FROM entries_fts WHERE rowid = ?", (entry_id,))
            except sqlite3.OperationalError:
                pass
            conn.commit()
        return True

    def search(self, query, category=None, tags=None, limit=10):
        if not query or not query.strip():
            return self.get_entries(category=category, limit=limit)
        cleaned = self._clean_fts_query(query)
        if not cleaned:
            return self.get_entries(category=category, limit=limit)
        sql = """SELECT e.id, e.topic, e.summary, c.name as category,
                        e.confidence, e.quality_score, e.access_count, e.created_at
                 FROM entries_fts fts
                 JOIN entries e ON fts.rowid = e.id
                 LEFT JOIN categories c ON e.category_id = c.id
                 WHERE entries_fts MATCH ?"""
        params = [cleaned]
        if category:
            sql += " AND c.name = ?"
            params.append(category)
        if tags:
            placeholders = ",".join("?" for _ in tags)
            sql += f" AND e.id IN (SELECT entry_id FROM tags WHERE tag IN ({placeholders}))"
            params.extend(tags)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            with self._conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                results = []
                for row in rows:
                    entry_tags = [r[0] for r in conn.execute("SELECT tag FROM tags WHERE entry_id = ?", (row[0],)).fetchall()]
                    results.append({"id": row[0], "topic": row[1], "summary": row[2][:300],
                                    "category": row[3], "confidence": row[4],
                                    "quality_score": row[5], "access_count": row[6],
                                    "created_at": row[7], "tags": entry_tags})
                return results
        except sqlite3.OperationalError:
            return self._fallback_search(query, category, tags, limit)

    def _fallback_search(self, query, category=None, tags=None, limit=10):
        with self._conn() as conn:
            sql = """SELECT e.id, e.topic, e.summary, c.name as category,
                            e.confidence, e.quality_score, e.access_count, e.created_at
                     FROM entries e LEFT JOIN categories c ON e.category_id = c.id
                     WHERE (e.topic LIKE ? OR e.summary LIKE ? OR e.content LIKE ?)"""
            like = f"%{query}%"
            params = [like, like, like]
            if category:
                sql += " AND c.name = ?"
                params.append(category)
            if tags:
                placeholders = ",".join("?" for _ in tags)
                sql += f" AND e.id IN (SELECT entry_id FROM tags WHERE tag IN ({placeholders}))"
                params.extend(tags)
            sql += " ORDER BY e.access_count DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            results = [{"id": r[0], "topic": r[1], "summary": r[2][:300],
                        "category": r[3], "confidence": r[4],
                        "quality_score": r[5], "access_count": r[6],
                        "created_at": r[7],
                        "tags": [t[0] for t in conn.execute("SELECT tag FROM tags WHERE entry_id = ?", (r[0],)).fetchall()]}
                       for r in rows]
            return results

    def _clean_fts_query(self, query):
        q = query.strip().lower()
        q = re.sub(r'[^a-z0-9\s]', ' ', q)
        q = re.sub(r'\s+', ' ', q).strip()
        if not q:
            return ""
        terms = q.split()
        if len(terms) == 1:
            return f"{terms[0]}*"
        return " AND ".join(f"{t}*" for t in terms)

    def get_context(self, query=None, categories=None, limit=5):
        if query and query.strip():
            results = self.search(query, limit=limit)
        else:
            results = self.get_entries(sort="access_count", limit=limit)
        if categories:
            results = [r for r in results if r["category"] in categories]
        if not results:
            return ""
        parts = []
        for r in results:
            tags_str = f" [{', '.join(r['tags'])}]" if r.get("tags") else ""
            parts.append(f"### {r['topic']}{tags_str}\nCategory: {r['category']}\n{r['summary'][:500]}")
        return "\n\n".join(parts)

    def get_entries(self, category=None, sort="recency", limit=50, offset=0):
        sql = """SELECT e.id, e.topic, e.summary, c.name as category,
                        e.confidence, e.quality_score, e.access_count, e.created_at
                 FROM entries e LEFT JOIN categories c ON e.category_id = c.id"""
        params = []
        if category:
            sql += " WHERE c.name = ?"
            params.append(category)
        if sort == "recency":
            sql += " ORDER BY e.created_at DESC"
        elif sort == "popularity":
            sql += " ORDER BY e.access_count DESC"
        elif sort == "quality":
            sql += " ORDER BY e.quality_score DESC, e.confidence DESC"
        else:
            sql += " ORDER BY e.created_at DESC"
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = [{"id": r[0], "topic": r[1], "summary": r[2][:200],
                        "category": r[3], "confidence": r[4],
                        "quality_score": r[5], "access_count": r[6],
                        "created_at": r[7],
                        "tags": [t[0] for t in conn.execute("SELECT tag FROM tags WHERE entry_id = ?", (r[0],)).fetchall()]}
                       for r in rows]
            return results

    def random_entries(self, count=3):
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT e.id, e.topic, e.summary, c.name as category
                FROM entries e LEFT JOIN categories c ON e.category_id = c.id
                ORDER BY RANDOM() LIMIT ?""", (count,)).fetchall()
            return [{"id": r[0], "topic": r[1], "summary": r[2][:200], "category": r[3]} for r in rows]

    def get_categories(self):
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT c.id, c.name, c.description, COUNT(e.id) as entry_count
                FROM categories c LEFT JOIN entries e ON e.category_id = c.id
                GROUP BY c.id ORDER BY entry_count DESC""").fetchall()
            return [{"id": r[0], "name": r[1], "description": r[2], "entry_count": r[3]} for r in rows]

    def get_tags(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT tag, COUNT(*) as cnt FROM tags GROUP BY tag ORDER BY cnt DESC LIMIT 100").fetchall()
            return {r[0]: r[1] for r in rows}

    def stats(self):
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            by_category = {}
            for row in conn.execute("SELECT c.name, COUNT(e.id) as cnt FROM categories c LEFT JOIN entries e ON e.category_id = c.id GROUP BY c.id ORDER BY cnt DESC").fetchall():
                by_category[row[0]] = row[1]
            oldest = conn.execute("SELECT topic, created_at FROM entries ORDER BY created_at ASC LIMIT 1").fetchone()
            newest = conn.execute("SELECT topic, created_at FROM entries ORDER BY created_at DESC LIMIT 1").fetchone()
            total_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            total_tags = conn.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0]
            return {"total_entries": total, "entries_by_category": by_category,
                    "total_sources": total_sources, "total_tags": total_tags,
                    "oldest_entry": {"topic": oldest[0], "created_at": oldest[1]} if oldest else None,
                    "newest_entry": {"topic": newest[0], "created_at": newest[1]} if newest else None,
                    "db_path": self.db_path,
                    "db_size_mb": round(os.path.getsize(self.db_path) / (1024 * 1024), 2) if os.path.exists(self.db_path) else 0}

    def migrate_from_legacy(self, training_dir=None):
        training_dir = training_dir or TRAINING_DIR
        results = {"processed": 0, "skipped": 0, "errors": 0, "details": []}
        if not os.path.exists(training_dir):
            results["details"].append({"file": "N/A", "status": "error", "message": f"Directory not found: {training_dir}"})
            return results
        for fname in sorted(os.listdir(training_dir)):
            if not fname.endswith("_memory.json"):
                continue
            fpath = os.path.join(training_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                results["errors"] += 1
                results["details"].append({"file": fname, "status": "error", "message": str(e)})
                continue
            category = self._infer_category(fname, data)
            kb = data.get("knowledge_base", [])
            for entry in kb:
                topic = entry.get("topic", "").strip()
                insight = entry.get("insight", "").strip()
                if not topic or not insight:
                    results["skipped"] += 1
                    continue
                topic_short = self._shorten_topic(topic)
                source_urls = re.findall(r'https?://[^\s,\]]+', insight)
                try:
                    self.add_entry(topic=topic_short, summary=insight[:2000], content=insight,
                                   category=category, tags=self._extract_tags(topic, category),
                                   sources=[{"url": u, "title": ""} for u in source_urls[:5]], confidence=0.5)
                    results["processed"] += 1
                except Exception as e:
                    results["errors"] += 1
                    results["details"].append({"file": fname, "topic": topic_short, "status": "error", "message": str(e)})
            results["details"].append({"file": fname, "status": "ok", "entries": len(kb)})
        return results

    def _infer_category(self, fname, data):
        fname_lower = fname.lower()
        mapping = {"coding": "coding", "python": "coding", "html": "coding",
                   "historical": "history", "agi": "agi", "technology": "technology",
                   "techs": "technology", "human_nature": "human_nature",
                   "human nature": "human_nature", "behavior": "human_nature", "medical": "medical"}
        for key, val in mapping.items():
            if key in fname_lower:
                return val
        topics = data.get("topics_covered", [])
        topic_text = " ".join(topics[:5]).lower() if topics else ""
        if any(w in topic_text for w in ["code", "python", "javascript", "programming"]):
            return "coding"
        if any(w in topic_text for w in ["history", "century", "empire", "dynasty"]):
            return "history"
        if any(w in topic_text for w in ["agi", "general intelligence", "consciousness"]):
            return "agi"
        if any(w in topic_text for w in ["technology", "quantum", "neural", "ai"]):
            return "technology"
        if any(w in topic_text for w in ["human", "brain", "behavior", "social"]):
            return "human_nature"
        return "general"

    def _shorten_topic(self, topic, max_words=15):
        words = topic.split()
        return " ".join(words[:max_words]) + "..." if len(words) > max_words else topic

    def _extract_tags(self, topic, category):
        topic_lower = topic.lower()
        tag_keywords = {"python", "javascript", "java", "rust", "go", "html", "css",
                        "machine learning", "deep learning", "neural network",
                        "quantum", "cybersecurity", "blockchain", "aws", "docker",
                        "api", "database", "sql", "nosql",
                        "psychology", "neuroscience", "cognition", "emotion",
                        "history", "philosophy", "ethics",
                        "algorithm", "optimization", "parallel", "distributed"}
        found = set()
        for kw in tag_keywords:
            if kw in topic_lower:
                found.add(kw)
        if category:
            found.add(category)
        return list(found)[:8]

    def rebuild_fts(self):
        with self._conn() as conn:
            try:
                conn.execute("DELETE FROM entries_fts")
                rows = conn.execute("SELECT id, topic, summary, content FROM entries").fetchall()
                for row in rows:
                    conn.execute("INSERT INTO entries_fts (rowid, topic, summary, content) VALUES (?, ?, ?, ?)", row)
                conn.commit()
                return len(rows)
            except sqlite3.OperationalError:
                return 0

    def clear_all(self):
        with self._conn() as conn:
            conn.execute("DELETE FROM tags")
            conn.execute("DELETE FROM sources")
            conn.execute("DELETE FROM entries")
            try:
                conn.execute("DELETE FROM entries_fts")
            except sqlite3.OperationalError:
                pass
            conn.commit()
