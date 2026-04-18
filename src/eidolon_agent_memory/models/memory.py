from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from eidolon_agent_memory.core.config import settings
from eidolon_agent_memory.models.base import Base

_DIM = settings.embedding_dimensions


class MemoryNode(Base):
    __tablename__ = "memory_nodes"
    __table_args__ = (
        UniqueConstraint("user_id", "companion_id", "node_type", "canonical_name"),
        Index(
            "ix_memory_nodes_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    companion_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companions.id", ondelete="CASCADE"),
        nullable=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="entity"
    )  # entity/event/concept/emotion
    label: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(_DIM), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MemoryEdge(Base):
    __tablename__ = "memory_edges"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "companion_id", "source_node_id", "target_node_id", "predicate"
        ),
        Index(
            "ix_memory_edges_fact_text_trgm",
            "fact_text",
            postgresql_using="gin",
            postgresql_ops={"fact_text": "gin_trgm_ops"},
        ),
        Index(
            "ix_memory_edges_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_memory_edges_user_companion", "user_id", "companion_id"),
        Index("ix_memory_edges_importance", "importance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    companion_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companions.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    predicate: Mapped[str] = mapped_column(String(64), nullable=False)
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(_DIM), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reasoning_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="explicit"
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    temporal_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="stable"
    )
    effective_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_edges.id", ondelete="SET NULL"),
        nullable=True,
    )
    emotional_context: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # HIGH = grief/trauma/major transitions, MED = milestones/goals, LOW = routine facts
    emotional_salience: Mapped[str] = mapped_column(
        String(8), nullable=False, default="LOW"
    )
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="user"
    )  # user/shared/companion
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual"
    )  # chat/manual/import
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    retrieval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EpisodicMemory(Base):
    __tablename__ = "episodic_memories"
    __table_args__ = (
        Index(
            "ix_episodic_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_episodic_user_companion", "user_id", "companion_id"),
    )

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
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(_DIM), nullable=True)
    # conversation/reflection/diary/dream/musing/narrative/insight_synthesis
    memory_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="conversation"
    )
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    mentioned_node_ids: Mapped[list | None] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=True
    )
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
