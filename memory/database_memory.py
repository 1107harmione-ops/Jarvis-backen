"""Database Memory - SQLite-backed short-term and long-term memory store."""

import sqlite3
import json
import os
import time
import threading
from datetime import datetime


class DatabaseMemory:
    """Persistent memory using SQLite for conversation history and knowledge."""

    def __init__(self, db_path: str = "data/memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodic_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_long_term_key
                ON long_term_memory(key);
            CREATE INDEX IF NOT EXISTS idx_episodic_session
                ON episodic_events(session_id, timestamp);
        """)
        conn.commit()

    # --- Short-term (conversation) memory ---

    def store_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, time.time(), json.dumps(metadata or {}))
        )
        conn.commit()

    def get_conversation_history(self, session_id: str, limit: int = 50) -> list:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
                for r in reversed(rows)]

    def get_recent_context(self, session_id: str, max_tokens: int = 4000) -> str:
        """Return recent conversation context as a formatted string, respecting token budget."""
        messages = self.get_conversation_history(session_id, limit=50)
        context_parts = []
        char_budget = max_tokens * 4  # rough estimate
        chars_used = 0

        for msg in messages:
            formatted = f"{msg['role']}: {msg['content']}"
            if chars_used + len(formatted) > char_budget:
                break
            context_parts.append(formatted)
            chars_used += len(formatted)

        return "\n".join(reversed(context_parts))

    # --- Long-term memory ---

    def store_fact(self, key: str, value: str, category: str = "general", importance: int = 1):
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            "INSERT INTO long_term_memory (key, value, category, importance, created, updated) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (key, value, category, importance, now, now)
        )
        conn.commit()

    def get_fact(self, key: str) -> str:
        conn = self._get_conn()
        cursor = conn.execute("SELECT value FROM long_term_memory WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    def search_facts(self, query: str, category: str = None, limit: int = 10) -> list:
        conn = self._get_conn()
        sql = "SELECT key, value, category, importance FROM long_term_memory WHERE (key LIKE ? OR value LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(sql, params)
        return [{"key": r["key"], "value": r["value"], "category": r["category"],
                 "importance": r["importance"]} for r in cursor.fetchall()]

    def get_all_facts(self, category: str = None, limit: int = 100) -> list:
        conn = self._get_conn()
        if category:
            cursor = conn.execute(
                "SELECT key, value, category, importance FROM long_term_memory "
                "WHERE category = ? ORDER BY importance DESC LIMIT ?",
                (category, limit)
            )
        else:
            cursor = conn.execute(
                "SELECT key, value, category, importance FROM long_term_memory "
                "ORDER BY importance DESC LIMIT ?", (limit,)
            )
        return [{"key": r["key"], "value": r["value"], "category": r["category"],
                 "importance": r["importance"]} for r in cursor.fetchall()]

    # --- Episodic memory ---

    def store_episode(self, session_id: str, event_type: str, summary: str, details: dict = None):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO episodic_events (session_id, event_type, summary, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (session_id, event_type, summary, json.dumps(details or {}), time.time())
        )
        conn.commit()

    def get_recent_episodes(self, session_id: str, limit: int = 20) -> list:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT event_type, summary, details, timestamp FROM episodic_events "
            "WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        return [{"type": r["event_type"], "summary": r["summary"],
                 "details": json.loads(r["details"]), "timestamp": r["timestamp"]}
                for r in cursor.fetchall()]

    def get_all_episodes(self, limit: int = 100) -> list:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT session_id, event_type, summary, timestamp FROM episodic_events "
            "ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [{"session_id": r["session_id"], "type": r["event_type"],
                 "summary": r["summary"], "timestamp": r["timestamp"]}
                for r in cursor.fetchall()]

    def cleanup_old_conversations(self, max_age_days: int = 30):
        """Remove conversation history older than max_age_days."""
        conn = self._get_conn()
        cutoff = time.time() - (max_age_days * 86400)
        conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
        conn.commit()
