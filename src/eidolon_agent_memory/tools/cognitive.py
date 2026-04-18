"""
Cognitive generation tools: generate_diary, generate_dream, generate_musing,
generate_insights, refresh_journal, extract_session_facts.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.services.cognitive import (
    generate_diary,
    generate_dream,
    generate_insights,
    generate_musing,
    refresh_journal,
)
from eidolon_agent_memory.services.extraction import extract_facts


async def tool_generate_diary(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Generate a diary entry from the companion's perspective about recent interactions.

    Use for: daily reflection; scheduled background task.
    Do NOT use: mid-conversation or on every session end.
    """
    mem = await generate_diary(db, user_id=user_id, companion_id=companion_id)
    return {"memory_id": str(mem.id), "text": mem.text, "memory_type": "diary"}


async def tool_generate_dream(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Generate a surreal dream narrative blending known facts about the user.

    Use for: morning check-in; scheduled background task.
    Do NOT use: more than once per day per companion.
    """
    mem = await generate_dream(db, user_id=user_id, companion_id=companion_id)
    return {"memory_id": str(mem.id), "text": mem.text, "memory_type": "dream"}


async def tool_generate_musing(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Generate a short spontaneous thought or observation from the companion.

    Use for: proactive message to user (idle time); scheduled background task.
    Do NOT use: inside an ongoing conversation response.
    """
    mem = await generate_musing(db, user_id=user_id, companion_id=companion_id)
    return {"memory_id": str(mem.id), "text": mem.text, "memory_type": "musing"}


async def tool_generate_insights(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Analyse stored facts and generate psychological/behavioural insights.

    Use for: after significant fact accumulation (>20 facts) or weekly synthesis.
    Do NOT use: with fewer than 10 stored facts (output will be low quality).
    """
    insights = await generate_insights(db, user_id=user_id, companion_id=companion_id)
    return {
        "insights": [
            {
                "id": str(i.id),
                "content": i.content,
                "category": i.category,
                "confidence": i.confidence,
            }
            for i in insights
        ],
        "count": len(insights),
    }


async def tool_refresh_journal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Rebuild/update the companion's journal about the user.

    Use for: weekly scheduled maintenance; after major new fact acquisition.
    Do NOT use: on every session — journal refresh is expensive.
    """
    journal = await refresh_journal(db, user_id=user_id, companion_id=companion_id)
    return {
        "journal_id": str(journal.id),
        "version": journal.version,
        "length": len(journal.content),
    }


async def tool_extract_session_facts(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    conversation_text: str,
    session_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Extract and persist structured facts from a conversation segment.

    Use for: after a session ends; processing conversation history.
    Do NOT use: mid-conversation or on short exchanges (<3 turns).
    conversation_text: full conversation as "User: ...\nAssistant: ..." format.
    """
    counts = await extract_facts(
        db,
        user_id=user_id,
        companion_id=companion_id,
        conversation_text=conversation_text,
        source_session_id=session_id,
    )
    return counts
