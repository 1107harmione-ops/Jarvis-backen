from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from backend.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id = Column(String(128), unique=True, nullable=False, index=True)
    device_name = Column(String(255))
    device_type = Column(String(64))  # android, web, ios
    fcm_token = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)
    last_seen = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", backref="devices")
