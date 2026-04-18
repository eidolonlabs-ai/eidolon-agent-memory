"""
Memory decay and deduplication services.

decay: slowly reduce importance scores of old, unretrieved facts.
dedup: merge near-duplicate facts using pg_trgm similarity.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.memory import MemoryEdge


# ── Decay ─────────────────────────────────────────────────────────────────────


async def decay_edges(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    decay_rate: float = 0.02,
    floor: float = 0.05,
) -> int:
    """
    Reduce importance of edges not retrieved recently.
    importance = max(floor, importance * (1 - decay_rate))
    Skips HIGH emotional salience edges.
    Returns count of rows updated.
    """
    result = await db.execute(
        update(MemoryEdge)
        .where(
            MemoryEdge.user_id == user_id,
            MemoryEdge.companion_id == companion_id,
            MemoryEdge.superseded_by.is_(None),
            MemoryEdge.emotional_salience != "HIGH",
        )
        .values(
            importance=text(
                f"GREATEST({floor}, importance * {1 - decay_rate})"
            )
        )
        .returning(MemoryEdge.id)
    )
    rows = result.fetchall()
    await db.commit()
    return len(rows)


# ── Dedup ─────────────────────────────────────────────────────────────────────


async def dedup_edges(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    similarity_threshold: float = 0.85,
) -> int:
    """
    Find near-duplicate fact_text pairs using pg_trgm similarity.
    For each duplicate pair keep the one with higher confidence; supersede the other.
    Returns number of edges superseded.
    """
    sql = text("""
        SELECT a.id AS a_id, b.id AS b_id,
               a.confidence AS a_conf, b.confidence AS b_conf
        FROM memory_edges a
        JOIN memory_edges b ON a.id < b.id
        WHERE a.user_id = :user_id
          AND b.user_id = :user_id
          AND a.companion_id IS NOT DISTINCT FROM :companion_id::uuid
          AND b.companion_id IS NOT DISTINCT FROM :companion_id::uuid
          AND a.superseded_by IS NULL
          AND b.superseded_by IS NULL
          AND similarity(a.fact_text, b.fact_text) > :threshold
    """)
    result = await db.execute(
        sql,
        {
            "user_id": str(user_id),
            "companion_id": str(companion_id),
            "threshold": similarity_threshold,
        },
    )
    pairs = result.fetchall()

    superseded = 0
    for row in pairs:
        # Keep the higher-confidence one; supersede the lower
        if row.a_conf >= row.b_conf:
            winner_id, loser_id = row.a_id, row.b_id
        else:
            winner_id, loser_id = row.b_id, row.a_id

        await db.execute(
            update(MemoryEdge)
            .where(MemoryEdge.id == loser_id, MemoryEdge.user_id == user_id)
            .values(superseded_by=winner_id)
        )
        superseded += 1

    if superseded:
        await db.commit()
    return superseded
