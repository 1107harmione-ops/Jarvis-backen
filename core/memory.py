import sqlite3
import os
import json
import threading
from datetime import datetime

class Memory:
    def __init__(self, db_file=None):
        HOME = os.path.expanduser("~")
        DATA_DIR = os.environ.get("JARVIS_NOTES_DIR", os.path.join(HOME, ".jarvis_data"))
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_file = db_file or os.path.join(DATA_DIR, "jarvis_memory.db")
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                role TEXT,
                                content TEXT,
                                session_id TEXT DEFAULT NULL
                            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_facts (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                fact_key TEXT UNIQUE,
                                fact_value TEXT,
                                fact_type TEXT DEFAULT 'personal',
                                priority INTEGER DEFAULT 1,
                                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS task_log (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                task TEXT,
                                status TEXT
                            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
                                id TEXT PRIMARY KEY,
                                name TEXT DEFAULT '',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                message_count INTEGER DEFAULT 0,
                                last_preview TEXT DEFAULT ''
                            )''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_facts_key ON user_facts(fact_key)')
            cursor.execute("PRAGMA table_info(user_facts)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'fact_type' not in columns:
                cursor.execute("ALTER TABLE user_facts ADD COLUMN fact_type TEXT DEFAULT 'personal'")
            if 'priority' not in columns:
                cursor.execute("ALTER TABLE user_facts ADD COLUMN priority INTEGER DEFAULT 1")
            if 'last_updated' not in columns:
                cursor.execute("ALTER TABLE user_facts ADD COLUMN last_updated DATETIME")
                cursor.execute("UPDATE user_facts SET last_updated = CURRENT_TIMESTAMP")
            conn.commit()

    def add(self, role, content):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
            conn.commit()

    def get_recent_chat(self, limit=20):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def learn_fact(self, key, value, fact_type='personal', priority=1):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_facts (fact_key, fact_value, fact_type, priority, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(fact_key) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    priority = MAX(priority, excluded.priority),
                    last_updated = CURRENT_TIMESTAMP
            ''', (key, value, fact_type, priority))
            conn.commit()

    def get_facts(self, fact_type=None):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            if fact_type:
                cursor.execute("SELECT fact_key, fact_value FROM user_facts WHERE fact_type = ? ORDER BY priority DESC", (fact_type,))
            else:
                cursor.execute("SELECT fact_key, fact_value FROM user_facts ORDER BY priority DESC")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def search_facts(self, query):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            q = f"%{query}%"
            cursor.execute("SELECT fact_key, fact_value FROM user_facts WHERE fact_key LIKE ? OR fact_value LIKE ?", (q, q))
            return {row[0]: row[1] for row in cursor.fetchall()}

    def add_task(self, task, status="completed"):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO task_log (task, status) VALUES (?, ?)", (task, status))
            conn.commit()

    def get_task_history(self, limit=10):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT task, status, timestamp FROM task_log ORDER BY id DESC LIMIT ?", (limit,))
            return [{"task": r[0], "status": r[1], "time": r[2]} for r in cursor.fetchall()]

    def clear(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history")
            cursor.execute("DELETE FROM user_facts")
            cursor.execute("DELETE FROM task_log")
            conn.commit()

    # ── Session Management ──

    def create_session(self, session_id, name=""):
        """Create a session if it doesn't already exist."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO sessions (id, name) VALUES (?, ?)", (session_id, name))
            conn.commit()

    def update_session(self, session_id, preview="", count=1):
        """Update a session's metadata (last preview text and message count increment)."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP, last_preview = ?, "
                "message_count = message_count + ? WHERE id = ?",
                (preview, count, session_id)
            )
            conn.commit()

    def add_with_session(self, role, content, session_id=None):
        """Insert a chat message, optionally associated with a session."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute(
                    "INSERT INTO chat_history (role, content, session_id) VALUES (?, ?, ?)",
                    (role, content, session_id)
                )
            else:
                cursor.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
            conn.commit()

    def get_sessions(self, limit=20):
        """Return the most recently updated sessions."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, created_at, updated_at, message_count, last_preview "
                "FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [
                {"id": r[0], "name": r[1], "created_at": r[2], "updated_at": r[3],
                 "message_count": r[4], "last_preview": r[5]}
                for r in cursor.fetchall()
            ]

    def get_session_messages(self, session_id):
        """Return all messages for a given session in chronological order."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in cursor.fetchall()]

    def delete_session(self, session_id):
        """Delete a session and all its associated messages."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    def get_session_history(self, session_id, limit=30):
        """Return the last N messages for a given session in chronological order."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, timestamp FROM chat_history "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]

    def clear_session(self, session_id):
        """Clear all messages for a session but keep the session record."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            cursor.execute(
                "UPDATE sessions SET message_count = 0, last_preview = '', "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            conn.commit()

    def get(self, limit=20):
        return self.get_recent_chat(limit)
