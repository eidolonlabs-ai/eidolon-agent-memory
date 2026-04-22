"""
Memory READ tools: search_memory, get_context, lookup_fact, get_relationship,
get_episodic, get_journal.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.insight import CompanionJournal, UserInsight
from eidolon_agent_memory.models.preference import Preference
from eidolon_agent_memory.models.relationship import Relationship
from eidolon_agent_memory.services.search import (
    SearchIntent,
    search_edges,
    search_episodic,
)


async def tool_search_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    query: str,
    intent: str = "factual",
    limit: int = 10,
) -> dict[str, Any]:
    """
    Semantic + hybrid search over memory facts (edges).

    Use for: "what do I know about X?", recalling facts for a response.
    Do NOT use: for casual greetings, for listing all facts (use get_context instead).

    intent: factual | emotional | casual | recall
    """
    results = await search_edges(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query=query,
        intent=intent,  # type: ignore[arg-type]
        limit=limit,
    )
    return {
        "facts": [
            {
                "id": r.id,
                "fact_text": r.fact_text,
                "predicate": r.predicate,
                "category": r.category,
                "emotional_salience": r.emotional_salience,
                "emotional_context": r.emotional_context,
                "importance": r.importance,
                "confidence": r.confidence,
                "scope": r.scope,
                "score": round(r.score, 4),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ],
        "count": len(results),
    }


async def tool_get_context(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    query: str,
    intent: str = "factual",
) -> dict[str, Any]:
    """
    Get structured context for responding: top facts, emotional facts, and
    recent episodic memories — formatted for prompt injection.

    Use for: building a context block before generating a response.
    Do NOT use: when only a single fact lookup is needed (use search_memory).
    """
    edges = await search_edges(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query=query,
        intent=intent,  # type: ignore[arg-type]
        limit=15,
    )
    episodic = await search_episodic(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query=query,
        intent=intent,  # type: ignore[arg-type]
        limit=5,
    )

    high_salience = [e for e in edges if e.emotional_salience == "HIGH"]
    regular = [e for e in edges if e.emotional_salience != "HIGH"]

    sections: list[str] = []
    if regular:
        facts_block = "\n".join(f"• {e.fact_text}" for e in regular[:8])
        sections.append(f"Facts:\n{facts_block}")
    if high_salience:
        em_block = "\n".join(
            f"• [{e.emotional_context or 'emotional'}] {e.fact_text}"
            for e in high_salience
        )
        sections.append(f"Emotional Context (HIGH salience):\n{em_block}")
    if episodic:
        mem_block = "\n".join(f"• {e.text[:200]}" for e in episodic[:3])
        sections.append(f"Recent Memories:\n{mem_block}")

    return {"context": "\n\n".join(sections), "fact_count": len(edges)}


async def tool_lookup_fact(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    subject: str,
    predicate: str | None = None,
) -> dict[str, Any]:
    """
    Exact/fuzzy fact lookup by subject name and optional predicate.

    Use for: "what is the user's job?", "does the user have siblings?".
    Do NOT use: open-ended semantic search (use search_memory).
    """
    from sqlalchemy import or_
    from eidolon_agent_memory.models.memory import MemoryEdge, MemoryNode

    stmt = (
        select(MemoryEdge, MemoryNode)
        .join(MemoryNode, MemoryEdge.source_node_id == MemoryNode.id)
        .where(
            MemoryEdge.user_id == user_id,
            MemoryEdge.companion_id == companion_id,
            MemoryEdge.superseded_by.is_(None),
            or_(
                MemoryNode.canonical_name.ilike(f"%{subject.lower()}%"),
                MemoryNode.label.ilike(f"%{subject}%"),
            ),
        )
    )
    if predicate:
        stmt = stmt.where(MemoryEdge.predicate.ilike(f"%{predicate.upper()}%"))
    stmt = stmt.order_by(MemoryEdge.importance.desc()).limit(5)

    result = await db.execute(stmt)
    rows = result.fetchall()

    return {
        "facts": [
            {
                "id": str(row[0].id),
                "fact_text": row[0].fact_text,
                "predicate": row[0].predicate,
                "importance": row[0].importance,
                "confidence": row[0].confidence,
                "emotional_salience": row[0].emotional_salience,
            }
            for row in rows
        ]
    }


async def tool_get_relationship(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get the current relationship state (trust, closeness, milestones).

    Use for: personalising tone, deciding level of intimacy in responses.
    """
    result = await db.execute(
        select(Relationship).where(
            Relationship.user_id == user_id,
            Relationship.companion_id == companion_id,
        )
    )
    rel = result.scalar_one_or_none()
    if rel is None:
        return {"trust": 0.5, "closeness": 0.1, "interactions": 0, "milestones": []}
    return {
        "trust": rel.trust_score,
        "closeness": rel.closeness_score,
        "interactions": rel.interaction_count,
        "absence_streak_days": rel.absence_streak_days,
        "milestones": rel.milestones or [],
    }


async def tool_get_episodic(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    query: str,
    memory_types: list[str] | None = None,
    intent: str = "factual",
    limit: int = 5,
) -> dict[str, Any]:
    """
    Search episodic memories (conversations, diaries, dreams, musings).

    Use for: recalling past events, checking if a topic was discussed before.
    Do NOT use: for fact retrieval (use search_memory or lookup_fact).
    intent: factual | emotional | casual | recall
    """
    results = await search_episodic(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query=query,
        memory_types=memory_types,
        intent=intent,  # type: ignore[arg-type]
        limit=limit,
    )
    return {
        "memories": [
            {
                "id": r.id,
                "text": r.text,
                "memory_type": r.memory_type,
                "importance": r.importance,
                "score": round(r.score, 4),
            }
            for r in results
        ]
    }


async def tool_get_journal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Retrieve the companion's current journal (evolving document about the user).

    Use for: loading personal context before a long conversation.
    Do NOT use: on every message — only when starting a session or refreshing context.
    """
    result = await db.execute(
        select(CompanionJournal).where(
            CompanionJournal.user_id == user_id,
            CompanionJournal.companion_id == companion_id,
        )
    )
    journal = result.scalar_one_or_none()
    if journal is None:
        return {"journal": "", "version": 0}

    insights_result = await db.execute(
        select(UserInsight)
        .where(
            UserInsight.user_id == user_id,
            UserInsight.companion_id == companion_id,
        )
        .order_by(UserInsight.importance.desc())
        .limit(5)
    )
    insights = list(insights_result.scalars().all())

    prefs_result = await db.execute(
        select(Preference).where(
            Preference.user_id == user_id,
            Preference.companion_id == companion_id,
        )
    )
    prefs = list(prefs_result.scalars().all())

    return {
        "journal": journal.content,
        "version": journal.version,
        "top_insights": [
            {"content": i.content, "category": i.category} for i in insights
        ],
        "preferences": {p.key: p.value for p in prefs},
    }
