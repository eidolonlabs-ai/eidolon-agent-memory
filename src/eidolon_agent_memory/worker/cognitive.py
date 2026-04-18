"""
Cognitive background helpers used by the worker.
(Session expiry, embedding backfill, etc.)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.core.config import settings
from eidolon_agent_memory.models.memory import EpisodicMemory, MemoryEdge, MemoryNode
from eidolon_agent_memory.models.session import Session
from eidolon_agent_memory.services.embedding import embedding_service

log = logging.getLogger(__name__)


async def expire_idle_sessions(db: AsyncSession) -> int:
    """
    End sessions that have been idle longer than SESSION_IDLE_MINUTES.
    Returns count of sessions ended.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.session_idle_minutes)
    result = await db.execute(
        select(Session).where(
            Session.status == "active",
            Session.started_at < cutoff,
        )
    )
    sessions = list(result.scalars().all())
    for s in sessions:
        s.status = "ended"
        s.ended_at = datetime.now(timezone.utc)
    if sessions:
        await db.commit()
    return len(sessions)


async def backfill_embeddings(db: AsyncSession, batch_size: int = 50) -> int:
    """
    Embed any rows that are missing embeddings.
    Returns total rows updated.
    """
    total = 0

    # MemoryEdge
    result = await db.execute(
        select(MemoryEdge).where(MemoryEdge.embedding.is_(None)).limit(batch_size)
    )
    edges = list(result.scalars().all())
    if edges:
        texts = [e.fact_text for e in edges]
        embeddings = await embedding_service.embed_batch(texts)
        for edge, emb in zip(edges, embeddings):
            edge.embedding = emb
        await db.commit()
        total += len(edges)
        log.info("Backfilled %d edge embeddings", len(edges))

    # MemoryNode
    result = await db.execute(
        select(MemoryNode).where(MemoryNode.embedding.is_(None)).limit(batch_size)
    )
    nodes = list(result.scalars().all())
    if nodes:
        texts = [n.label for n in nodes]
        embeddings = await embedding_service.embed_batch(texts)
        for node, emb in zip(nodes, embeddings):
            node.embedding = emb
        await db.commit()
        total += len(nodes)
        log.info("Backfilled %d node embeddings", len(nodes))

    # EpisodicMemory
    result = await db.execute(
        select(EpisodicMemory)
        .where(EpisodicMemory.embedding.is_(None))
        .limit(batch_size)
    )
    episodes = list(result.scalars().all())
    if episodes:
        texts = [e.text[:512] for e in episodes]
        embeddings = await embedding_service.embed_batch(texts)
        for ep, emb in zip(episodes, embeddings):
            ep.embedding = emb
        await db.commit()
        total += len(episodes)
        log.info("Backfilled %d episodic embeddings", len(episodes))

    return total
