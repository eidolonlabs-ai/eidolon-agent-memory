"""CRUD helpers for memory nodes, edges, and episodic memories."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.memory import EpisodicMemory, MemoryEdge, MemoryNode
from eidolon_agent_memory.services.embedding import embedding_service


# ── MemoryNode ────────────────────────────────────────────────────────────────


async def upsert_node(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID | None,
    node_type: str,
    label: str,
    canonical_name: str,
    description: str | None = None,
    properties: dict | None = None,
    confidence: float = 1.0,
    importance: float = 0.5,
    embed: bool = True,
) -> MemoryNode:
    stmt = select(MemoryNode).where(
        MemoryNode.user_id == user_id,
        MemoryNode.companion_id == companion_id,
        MemoryNode.node_type == node_type,
        MemoryNode.canonical_name == canonical_name,
    )
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    embedding = await embedding_service.embed(label) if embed else None

    if node is None:
        node = MemoryNode(
            user_id=user_id,
            companion_id=companion_id,
            node_type=node_type,
            label=label,
            canonical_name=canonical_name,
            description=description,
            properties=properties,
            confidence=confidence,
            importance=importance,
            embedding=embedding,
        )
        db.add(node)
    else:
        node.label = label
        node.mention_count = (node.mention_count or 0) + 1
        node.last_verified_at = datetime.now(timezone.utc)
        if description:
            node.description = description
        if properties:
            node.properties = {**(node.properties or {}), **properties}
        if importance > node.importance:
            node.importance = importance
        if embedding:
            node.embedding = embedding

    await db.flush()
    return node


async def get_node_by_id(
    db: AsyncSession, node_id: uuid.UUID, user_id: uuid.UUID
) -> MemoryNode | None:
    result = await db.execute(
        select(MemoryNode).where(
            MemoryNode.id == node_id, MemoryNode.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


# ── MemoryEdge ────────────────────────────────────────────────────────────────


async def upsert_edge(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID | None,
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    predicate: str,
    fact_text: str,
    category: str | None = None,
    reasoning_type: str = "explicit",
    confidence: float = 1.0,
    importance: float = 0.5,
    temporal_type: str = "stable",
    emotional_context: str | None = None,
    emotional_salience: str = "LOW",
    scope: str = "user",
    source: str = "manual",
    source_session_id: uuid.UUID | None = None,
    source_message_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    embed: bool = True,
) -> MemoryEdge:
    stmt = select(MemoryEdge).where(
        MemoryEdge.user_id == user_id,
        MemoryEdge.companion_id == companion_id,
        MemoryEdge.source_node_id == source_node_id,
        MemoryEdge.target_node_id == target_node_id,
        MemoryEdge.predicate == predicate,
        MemoryEdge.fact_text == fact_text,
    )
    result = await db.execute(stmt)
    edge = result.scalar_one_or_none()

    embedding = await embedding_service.embed(fact_text) if embed else None

    if edge is None:
        edge = MemoryEdge(
            user_id=user_id,
            companion_id=companion_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            predicate=predicate,
            fact_text=fact_text,
            category=category,
            reasoning_type=reasoning_type,
            confidence=confidence,
            importance=importance,
            temporal_type=temporal_type,
            emotional_context=emotional_context,
            emotional_salience=emotional_salience,
            scope=scope,
            source=source,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            embedding=embedding,
        )
        if created_at is not None:
            edge.created_at = created_at
        if updated_at is not None:
            edge.updated_at = updated_at
        db.add(edge)
    else:
        # Update mutable fields; preserve history
        if confidence > edge.confidence:
            edge.confidence = confidence
        if importance > edge.importance:
            edge.importance = importance
        if emotional_salience in ("HIGH", "MED") and edge.emotional_salience == "LOW":
            edge.emotional_salience = emotional_salience
        if embedding:
            edge.embedding = embedding
        edge.fact_text = fact_text

    await db.flush()
    return edge


async def supersede_edge(
    db: AsyncSession,
    old_edge_id: uuid.UUID,
    new_edge_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await db.execute(
        update(MemoryEdge)
        .where(MemoryEdge.id == old_edge_id, MemoryEdge.user_id == user_id)
        .values(superseded_by=new_edge_id, resolved_at=datetime.now(timezone.utc))
    )


async def get_edge_by_id(
    db: AsyncSession, edge_id: uuid.UUID, user_id: uuid.UUID
) -> MemoryEdge | None:
    result = await db.execute(
        select(MemoryEdge).where(
            MemoryEdge.id == edge_id, MemoryEdge.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_edges_for_node(
    db: AsyncSession,
    node_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    include_superseded: bool = False,
    limit: int = 50,
) -> list[MemoryEdge]:
    stmt = select(MemoryEdge).where(
        MemoryEdge.user_id == user_id,
        (MemoryEdge.source_node_id == node_id)
        | (MemoryEdge.target_node_id == node_id),
    )
    if not include_superseded:
        stmt = stmt.where(MemoryEdge.superseded_by.is_(None))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── EpisodicMemory ────────────────────────────────────────────────────────────


async def create_episodic(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    text: str,
    memory_type: str = "conversation",
    importance: float = 0.5,
    confidence: float = 1.0,
    session_id: uuid.UUID | None = None,
    mentioned_node_ids: list[uuid.UUID] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    embed: bool = True,
) -> EpisodicMemory:
    embedding = await embedding_service.embed(text) if embed else None
    mem = EpisodicMemory(
        user_id=user_id,
        companion_id=companion_id,
        text=text,
        embedding=embedding,
        memory_type=memory_type,
        importance=importance,
        confidence=confidence,
        session_id=session_id,
        mentioned_node_ids=mentioned_node_ids,
        extra_metadata=extra_metadata,
    )
    db.add(mem)
    await db.flush()
    return mem


async def delete_episodic(
    db: AsyncSession, memory_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await db.execute(
        delete(EpisodicMemory).where(
            EpisodicMemory.id == memory_id, EpisodicMemory.user_id == user_id
        )
    )
