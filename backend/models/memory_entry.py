from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from backend.database import Base


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    memory_type = Column(String(32), default="episodic")  # episodic, semantic, procedural
    importance = Column(String(16), default="medium")  # low, medium, high, critical
    embedding = Column(VECTOR(384), nullable=True)  # pgvector embedding
    meta_data = Column("metadata", JSONB, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="memory_entries")
