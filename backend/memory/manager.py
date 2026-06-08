"""
Memory Management System
Types: episodic (conversation history), semantic (facts/knowledge), procedural (how-to)
Uses pgvector for similarity search when available, falls back to keyword matching.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.memory_entry import MemoryEntry
from backend.core.logging import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Manage different types of memory with vector search."""

    def __init__(self):
        self._embedding_model = None

    async def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding vector for text using sentence-transformers."""
        try:
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except ImportError:
            logger.warning("sentence-transformers not installed — vector search disabled")
            return None
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    async def store(
        self,
        db: AsyncSession,
        user_id: UUID,
        content: str,
        memory_type: str = "episodic",
        importance: str = "medium",
        metadata: dict = None,
        ttl_hours: Optional[int] = None,
    ) -> dict:
        """Store a new memory entry."""
        embedding = await self._get_embedding(content)

        expires_at = None
        if ttl_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        entry = MemoryEntry(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding,
            metadata=metadata or {},
            expires_at=expires_at,
        )
        db.add(entry)
        await db.flush()

        logger.debug(f"Memory stored: {memory_type}/{importance} — {content[:50]}...")
        return {"id": str(entry.id), "memory_type": memory_type, "importance": importance}

    async def search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search memories by semantic similarity or keyword match."""
        embedding = await self._get_embedding(query)

        if embedding:
            return await self._vector_search(db, user_id, embedding, memory_type, limit)
        else:
            return await self._keyword_search(db, user_id, query, memory_type, limit)

    async def _vector_search(
        self,
        db: AsyncSession,
        user_id: UUID,
        embedding: list[float],
        memory_type: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Perform vector similarity search using pgvector."""
        try:
            embedding_str = f"[{','.join(str(x) for x in embedding)}]"

            sql = """
                SELECT id, content, memory_type, importance, metadata, created_at,
                       1 - (embedding <=> :embedding::vector) as similarity
                FROM memory_entries
                WHERE user_id = :user_id
                AND (expires_at IS NULL OR expires_at > NOW())
            """
            params = {"user_id": user_id, "embedding": embedding_str}

            if memory_type:
                sql += " AND memory_type = :memory_type"
                params["memory_type"] = memory_type

            sql += " ORDER BY similarity DESC LIMIT :limit"
            params["limit"] = limit

            result = await db.execute(text(sql), params)
            rows = result.all()

            return [
                {
                    "id": str(r.id),
                    "content": r.content,
                    "memory_type": r.memory_type,
                    "importance": r.importance,
                    "similarity": float(r.similarity),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows if float(r.similarity) > 0.5
            ]

        except Exception as e:
            logger.warning(f"Vector search failed ({e}), falling back to keyword")
            return await self._keyword_search(db, user_id, "", memory_type, limit)

    async def _keyword_search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        memory_type: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Fallback keyword-based memory search."""
        stmt = select(MemoryEntry).where(
            MemoryEntry.user_id == user_id,
            (MemoryEntry.expires_at.is_(None)) | (MemoryEntry.expires_at > datetime.now(timezone.utc)),
        )

        if query:
            stmt = stmt.where(MemoryEntry.content.ilike(f"%{query}%"))
        if memory_type:
            stmt = stmt.where(MemoryEntry.memory_type == memory_type)

        stmt = stmt.order_by(MemoryEntry.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        entries = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "content": e.content,
                "memory_type": e.memory_type,
                "importance": e.importance,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    async def recall_recent(
        self,
        db: AsyncSession,
        user_id: UUID,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get most recent memories."""
        stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if memory_type:
            stmt = stmt.where(MemoryEntry.memory_type == memory_type)
        stmt = stmt.order_by(MemoryEntry.created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        entries = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "content": e.content,
                "memory_type": e.memory_type,
                "importance": e.importance,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    async def forget(self, db: AsyncSession, memory_id: UUID, user_id: UUID) -> bool:
        """Delete a specific memory."""
        result = await db.execute(
            select(MemoryEntry).where(
                MemoryEntry.id == memory_id,
                MemoryEntry.user_id == user_id,
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return False
        await db.delete(entry)
        return True


# Global instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
