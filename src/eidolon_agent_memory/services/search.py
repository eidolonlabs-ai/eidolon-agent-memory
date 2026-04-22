"""
Hybrid retrieval search service.

Scoring formula:
  score = 0.45 × cosine + 0.25 × recency_decay + 0.20 × importance + 0.10 × confidence

Salience gating (search_edges, emotional_salience):
  - intent=casual AND salience=HIGH AND cosine < 0.82  → score × 0.01 (near-suppress)
  - intent=casual AND salience=MED  AND cosine < 0.72  → score × 0.15
  - intent=emotional → HIGH × 1.5, MED × 1.2

Episodic suppression (search_episodic):
  - intent=casual AND memory_type IN (diary, dream) AND cosine < 0.70 → excluded from results

Cross-companion: always includes scope='shared' edges.
"""
from __future__ import annotations

from datetime import datetime
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.services.embedding import embedding_service

SearchIntent = Literal["casual", "emotional", "factual", "recall"]


@dataclass
class SearchResult:
    id: str
    fact_text: str
    predicate: str
    category: str | None
    emotional_salience: str
    emotional_context: str | None
    importance: float
    confidence: float
    scope: str
    score: float
    created_at: datetime | None


@dataclass
class EpisodicResult:
    id: str
    text: str
    memory_type: str
    importance: float
    score: float


# ── Edge search ───────────────────────────────────────────────────────────────


async def search_edges(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    query: str,
    intent: SearchIntent = "factual",
    limit: int = 20,
    min_score: float = 0.1,
) -> list[SearchResult]:
    """
    Hybrid retrieval for MemoryEdge rows.

    Scope rules:
    - Always includes scope='shared' (cross-companion facts)
    - Includes scope='user' for all companions of this user
    - Includes scope='companion' only for this specific companion
    """
    query_vec = await embedding_service.embed(query)
    vec_literal = f"[{','.join(str(x) for x in query_vec)}]"

    # Salience multiplier expression
    if intent == "casual":
        salience_expr = """
            CASE
                WHEN me.emotional_salience = 'HIGH' AND (1 - (me.embedding <=> CAST(:vec AS vector))) < 0.82
                    THEN 0.01
                WHEN me.emotional_salience = 'MED' AND (1 - (me.embedding <=> CAST(:vec AS vector))) < 0.72
                    THEN 0.15
                WHEN me.emotional_salience = 'HIGH' THEN 1.0
                WHEN me.emotional_salience = 'MED' THEN 1.0
                ELSE 1.0
            END
        """
    elif intent == "emotional":
        salience_expr = """
            CASE
                WHEN me.emotional_salience = 'HIGH' THEN 1.5
                WHEN me.emotional_salience = 'MED' THEN 1.2
                ELSE 1.0
            END
        """
    else:
        salience_expr = "1.0"

    if intent == "recall":
        # Emphasize recency for "lately/recent" style recall queries.
        score_expr = """
            0.40 * (1 - (me.embedding <=> CAST(:vec AS vector)))
            + 0.22 * ts_rank_cd(to_tsvector('english', COALESCE(me.fact_text, '')), plainto_tsquery('english', :query_text))
            + 0.30 * EXP(-EXTRACT(EPOCH FROM (NOW() - me.created_at)) / 2592000.0)
            + 0.06 * me.importance
            + 0.02 * me.confidence
        """
    else:
        # Improve top-k relevance by combining semantic and lexical signals.
        score_expr = """
            0.50 * (1 - (me.embedding <=> CAST(:vec AS vector)))
            + 0.20 * ts_rank_cd(to_tsvector('english', COALESCE(me.fact_text, '')), plainto_tsquery('english', :query_text))
            + 0.20 * EXP(-EXTRACT(EPOCH FROM (NOW() - me.created_at)) / 2592000.0)
            + 0.07 * me.importance
            + 0.03 * me.confidence
        """

    sql = text(f"""
        SELECT
            CAST(me.id AS TEXT) AS id,
            me.fact_text,
            me.predicate,
            me.category,
            me.emotional_salience,
            me.emotional_context,
            me.importance,
            me.confidence,
            me.scope,
            me.created_at,
            ({score_expr}) * ({salience_expr}) AS score
        FROM memory_edges me
        WHERE
            me.user_id = :user_id
            AND me.superseded_by IS NULL
            AND me.embedding IS NOT NULL
            AND (
                (me.companion_id = :companion_id AND me.scope IN ('user', 'companion'))
                OR me.scope = 'shared'
            )
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "user_id": str(user_id),
            "companion_id": str(companion_id),
            "vec": vec_literal,
            "query_text": query,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    out: list[SearchResult] = []
    for row in rows:
        if row.score < min_score:
            continue
        out.append(
            SearchResult(
                id=row.id,
                fact_text=row.fact_text,
                predicate=row.predicate,
                category=row.category,
                emotional_salience=row.emotional_salience,
                emotional_context=row.emotional_context,
                importance=row.importance,
                confidence=row.confidence,
                scope=row.scope,
                score=float(row.score),
                created_at=row.created_at,
            )
        )
    return out


# ── Episodic search ───────────────────────────────────────────────────────────


async def search_episodic(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    query: str,
    memory_types: list[str] | None = None,
    intent: SearchIntent = "factual",
    limit: int = 10,
    min_score: float = 0.1,
) -> list[EpisodicResult]:
    """Search episodic memories with optional intent-based filtering.
    
    Intent gating: when intent='casual', suppress diary/dream entries that
    are likely to contain high-salience crisis content, aligned with graceful
    omission requirements.
    """
    query_vec = await embedding_service.embed(query)
    vec_literal = f"[{','.join(str(x) for x in query_vec)}]"

    type_filter = ""
    params: dict = {
        "user_id": str(user_id),
        "companion_id": str(companion_id),
        "vec": vec_literal,
        "limit": limit,
    }

    if memory_types:
        type_filter = "AND em.memory_type = ANY(:memory_types)"
        params["memory_types"] = memory_types

    # For casual intent, suppress diary/dream entries unless they're semantically
    # relevant to the query (cosine >= 0.70). This prevents grief-laden diary/dream
    # entries from surfacing in casual contexts like "what fun things can we do?".
    # Note: importance threshold is intentionally omitted — diary=0.6, dream=0.5,
    # so an importance gate would never fire.
    suppress_expr = ""
    if intent == "casual":
        suppress_expr = """
            AND NOT (
                em.memory_type IN ('diary', 'dream')
                AND (1 - (em.embedding <=> CAST(:vec AS vector))) < 0.70
            )
        """

    sql = text(f"""
        SELECT
            CAST(em.id AS TEXT) AS id,
            em.text,
            em.memory_type,
            em.importance,
            (
                0.45 * (1 - (em.embedding <=> CAST(:vec AS vector)))
                + 0.25 * EXP(-EXTRACT(EPOCH FROM (NOW() - em.created_at)) / 2592000.0)
                + 0.20 * em.importance
                + 0.10 * em.confidence
            ) AS score
        FROM episodic_memories em
        WHERE
            em.user_id = :user_id
            AND em.companion_id = :companion_id
            AND em.embedding IS NOT NULL
            {type_filter}
            {suppress_expr}
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    out: list[EpisodicResult] = []
    for row in rows:
        if row.score < min_score:
            continue
        out.append(
            EpisodicResult(
                id=row.id,
                text=row.text,
                memory_type=row.memory_type,
                importance=row.importance,
                score=float(row.score),
            )
        )
    return out
