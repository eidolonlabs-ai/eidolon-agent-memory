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
    batch_size: int = 500,
) -> int:
    """
    Reduce importance of edges not retrieved recently.
    importance = max(floor, importance * (1 - decay_rate))
    Skips HIGH emotional salience edges.
    Processes in batches to avoid long-running transactions on large datasets.
    Returns total count of rows updated.
    """
    total_decayed = 0
    while True:
        subq = text("""
            SELECT id FROM memory_edges
            WHERE user_id = :user_id
              AND (companion_id IS NOT DISTINCT FROM :companion_id::uuid)
              AND superseded_by IS NULL
              AND emotional_salience != 'HIGH'
            LIMIT :batch_size
        """)
        sub_result = await db.execute(
            subq,
            {
                "user_id": str(user_id),
                "companion_id": str(companion_id),
                "batch_size": batch_size,
            },
        )
        batch_ids = [row.id for row in sub_result.fetchall()]
        if not batch_ids:
            break

        result = await db.execute(
            update(MemoryEdge)
            .where(
                MemoryEdge.id.in_(batch_ids),
                MemoryEdge.user_id == user_id,
            )
            .values(
                importance=text(
                    f"GREATEST({floor}, importance * {1 - decay_rate})"
                )
            )
            .returning(MemoryEdge.id)
        )
        rows = result.fetchall()
        total_decayed += len(rows)
        await db.commit()

        if len(batch_ids) < batch_size:
            break

    return total_decayed


# ── Dedup ─────────────────────────────────────────────────────────────────────


async def dedup_edges(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    similarity_threshold: float = 0.85,
    max_pairs: int = 200,
) -> int:
    """
    Find near-duplicate fact_text pairs using pg_trgm similarity.
    For each duplicate pair keep the one with higher confidence; supersede the other.
    Returns number of edges superseded.
    Capped at max_pairs to prevent O(n²) blowup on large datasets.
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
        ORDER BY similarity(a.fact_text, b.fact_text) DESC
        LIMIT :max_pairs
    """)
    result = await db.execute(
        sql,
        {
            "user_id": str(user_id),
            "companion_id": str(companion_id),
            "threshold": similarity_threshold,
            "max_pairs": max_pairs,
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
