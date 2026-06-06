"""Vector Memory - Semantic search using ChromaDB (SQLite fallback)."""

import json
import hashlib
import sqlite3
import os
import time
import threading

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


class VectorMemory:
    """Semantic memory with embeddings-based retrieval.

    Uses ChromaDB when available, falls back to SQLite keyword search.
    """

    def __init__(self, persist_dir: str = "data/vectormem"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self._local = threading.local()

        if HAS_CHROMADB:
            self._init_chromadb()
        else:
            self._init_fallback()

    def _get_chroma_client(self):
        if not hasattr(self._local, "chroma_client") or self._local.chroma_client is None:
            self._local.chroma_client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
        return self._local.chroma_client

    def _init_chromadb(self):
        try:
            client = self._get_chroma_client()
            try:
                self.collection = client.get_collection("jarvis_memories")
            except Exception:
                self.collection = client.create_collection("jarvis_memories")
        except Exception as e:
            print(f"[VectorMemory] ChromaDB init failed: {e}, using fallback")
            self._init_fallback()

    def _init_fallback(self):
        """SQLite-based keyword search fallback."""
        self._fallback_path = os.path.join(self.persist_dir, "fallback_memory.db")
        conn = self._get_fallback_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                category TEXT DEFAULT 'general',
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_content ON memories(content)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
        conn.commit()

    def _get_fallback_conn(self):
        if not hasattr(self._local, "fallback_conn") or self._local.fallback_conn is None:
            self._local.fallback_conn = sqlite3.connect(self._fallback_path)
        return self._local.fallback_conn

    def _make_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def store(self, content: str, metadata: dict = None, category: str = "general"):
        """Store a memory with embedding."""
        mem_id = self._make_id(content)

        if HAS_CHROMADB:
            try:
                client = self._get_chroma_client()
                col = client.get_collection("jarvis_memories")
                col.add(
                    documents=[content],
                    metadatas=[{"category": category, **(metadata or {})}],
                    ids=[mem_id]
                )
                return
            except Exception:
                pass

        # Fallback: store in SQLite
        conn = self._get_fallback_conn()
        conn.execute(
            "INSERT OR REPLACE INTO memories (id, content, metadata, category, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (mem_id, content, json.dumps(metadata or {}), category, time.time())
        )
        conn.commit()

    def search(self, query: str, category: str = None, n_results: int = 5) -> list:
        """Search for semantically similar memories."""
        if HAS_CHROMADB:
            try:
                client = self._get_chroma_client()
                col = client.get_collection("jarvis_memories")
                where = {"category": category} if category else None
                results = col.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where
                )
                if results["documents"] and results["documents"][0]:
                    return [
                        {"content": doc, "metadata": meta, "id": id_}
                        for doc, meta, id_ in zip(
                            results["documents"][0],
                            results["metadatas"][0] if results["metadatas"][0] else [{}] * len(results["documents"][0]),
                            results["ids"][0]
                        )
                    ]
            except Exception:
                pass

        # Fallback: keyword search
        conn = self._get_fallback_conn()
        words = query.lower().split()
        results = {}

        for word in words:
            cursor = conn.execute(
                "SELECT id, content, metadata, category FROM memories WHERE content LIKE ?",
                (f"%{word}%",)
            )
            for row in cursor.fetchall():
                if row[0] not in results:
                    results[row[0]] = {
                        "content": row[1],
                        "metadata": json.loads(row[2]),
                        "category": row[3],
                        "id": row[0],
                        "score": 0
                    }
                results[row[0]]["score"] += 1

        sorted_results = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:n_results]

    def count(self) -> int:
        """Return total number of stored memories."""
        if HAS_CHROMADB:
            try:
                client = self._get_chroma_client()
                col = client.get_collection("jarvis_memories")
                return col.count()
            except Exception:
                pass
        conn = self._get_fallback_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM memories")
        return cursor.fetchone()[0]

    def delete_old(self, max_age_days: int = 90):
        """Remove memories older than max_age_days."""
        cutoff = time.time() - (max_age_days * 86400)
        conn = self._get_fallback_conn()
        conn.execute("DELETE FROM memories WHERE timestamp < ?", (cutoff,))
        conn.commit()
