from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from eidolon_agent_memory.models.base import Base


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("user_id", "companion_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companions.id", ondelete="CASCADE"),
        nullable=False,
    )
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    closeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_user_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    milestones: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    absence_streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Stores companion-scoped preferences + pending decay probes
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
