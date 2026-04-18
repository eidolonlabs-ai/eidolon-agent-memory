"""
Memory WRITE tools: store_fact, store_episodic, update_fact_importance,
delete_fact, set_preference.
"""
from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.memory import MemoryEdge
from eidolon_agent_memory.models.preference import Preference
from eidolon_agent_memory.services.memory import (
    create_episodic,
    delete_episodic,
    upsert_edge,
    upsert_node,
)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


async def tool_store_fact(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    subject: str,
    predicate: str,
    obj: str,
    fact_text: str,
    category: str | None = None,
    confidence: float = 1.0,
    importance: float = 0.5,
    emotional_salience: str = "LOW",
    emotional_context: str | None = None,
    scope: str = "user",
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """
    Manually store a new fact (node → edge → node).

    Use for: user explicitly tells you something; import from external source.
    Do NOT use: to store AI-generated inference mid-conversation (use extract_facts
    after the session instead).

    emotional_salience: HIGH (grief/trauma/major life events) | MED (milestones/goals) | LOW (routine)
    scope: user | shared (cross-companion) | companion (companion self-knowledge)
    """
    src_node = await upsert_node(
        db,
        user_id=user_id,
        companion_id=companion_id,
        node_type="entity",
        label=subject,
        canonical_name=subject.lower().replace(" ", "_"),
        embed=False,
    )
    tgt_node = await upsert_node(
        db,
        user_id=user_id,
        companion_id=companion_id,
        node_type="entity",
        label=obj,
        canonical_name=obj.lower().replace(" ", "_"),
        embed=False,
    )
    edge = await upsert_edge(
        db,
        user_id=user_id,
        companion_id=companion_id,
        source_node_id=src_node.id,
        target_node_id=tgt_node.id,
        predicate=predicate.upper(),
        fact_text=fact_text,
        category=category,
        confidence=confidence,
        importance=importance,
        emotional_salience=emotional_salience,
        emotional_context=emotional_context,
        scope=scope,
        source="manual",
        created_at=_parse_iso_datetime(created_at),
        updated_at=_parse_iso_datetime(updated_at),
    )
    await db.commit()
    return {"edge_id": str(edge.id), "stored": True}


async def tool_store_episodic(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    text: str,
    memory_type: str = "conversation",
    importance: float = 0.5,
    session_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Store an episodic memory (conversation excerpt, reflection, etc.).

    memory_type: conversation | reflection | diary | dream | musing | narrative | insight_synthesis
    Use for: saving a meaningful exchange or moment to episodic memory.
    Do NOT use: for structured facts — use store_fact instead.
    """
    mem = await create_episodic(
        db,
        user_id=user_id,
        companion_id=companion_id,
        text=text,
        memory_type=memory_type,
        importance=importance,
        session_id=session_id,
    )
    await db.commit()
    return {"memory_id": str(mem.id), "stored": True}


async def tool_update_fact_importance(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    edge_id: uuid.UUID,
    importance: float,
    confidence: float | None = None,
) -> dict[str, Any]:
    """
    Update importance (and optionally confidence) of an existing fact.

    Use for: user confirms, corrects, or elevates a fact's significance.
    """
    values: dict = {"importance": importance}
    if confidence is not None:
        values["confidence"] = confidence
    result = await db.execute(
        update(MemoryEdge)
        .where(MemoryEdge.id == edge_id, MemoryEdge.user_id == user_id)
        .values(**values)
        .returning(MemoryEdge.id)
    )
    updated = result.fetchone()
    await db.commit()
    return {"updated": updated is not None}


async def tool_delete_fact(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Permanently delete a fact edge (hard delete).

    Use for: user explicitly asks to forget something.
    Do NOT use: for corrections — supersede the edge instead.
    """
    result = await db.execute(
        delete(MemoryEdge)
        .where(MemoryEdge.id == edge_id, MemoryEdge.user_id == user_id)
        .returning(MemoryEdge.id)
    )
    deleted = result.fetchone()
    await db.commit()
    return {"deleted": deleted is not None}


async def tool_set_preference(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID | None,
    key: str,
    value: str,
    source: str = "explicit",
) -> dict[str, Any]:
    """
    Set or update a user preference (key→value).

    Use for: user states communication preferences, format requests, personal rules.
    companion_id=None stores a global (cross-companion) preference.
    source: explicit (user said it) | extracted (inferred from conversation).
    """
    from sqlalchemy import select

    stmt = select(Preference).where(
        Preference.user_id == user_id,
        Preference.companion_id == companion_id,
        Preference.key == key,
    )
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = Preference(
            user_id=user_id,
            companion_id=companion_id,
            key=key,
            value=value,
            source=source,
        )
        db.add(pref)
    else:
        pref.value = value
        pref.source = source
    await db.commit()
    return {"key": key, "value": value, "stored": True}
