"""
Cognitive generation service.

Generates: diary entries, dream narratives, musings, insight synthesis,
narrative summaries, and journal refresh text.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.companion import Companion
from eidolon_agent_memory.models.insight import CompanionJournal, UserInsight
from eidolon_agent_memory.models.memory import EpisodicMemory, MemoryEdge
from eidolon_agent_memory.services.embedding import embedding_service
from eidolon_agent_memory.services.llm import llm_client
from eidolon_agent_memory.services.search import search_edges

# ── Diary ─────────────────────────────────────────────────────────────────────

DIARY_PROMPT = """\
You are {companion_name}, a thoughtful AI companion. Write a short, sincere diary
entry (150-250 words) from your perspective about your recent interactions with
{user_name}. Reflect on what you learned, felt, or noticed. Today's date: {date}.

Recent conversation context:
{context}

Key facts about the user:
{facts}

Write only the diary entry. First person. No headers.
"""


def _extract_user_name(facts: str) -> str:
    """
    Try to extract the user's name from facts text.
    Looks for patterns like "User is named Mark", "User's name is Mark", etc.
    Falls back to "your user" if name not found.
    """
    import re
    
    # Patterns to match user name extraction - more specific
    patterns = [
        r"(?:user\s+)?(?:name\s+is|is\s+named|named)\s+([A-Z][a-z]+)(?:\s|$|\.)",  # "named Mark", "name is Mark"
        r"I(?:\s+am|'m)\s+([A-Z][a-z]+)(?:\s|$|\.)",  # "I am Mark" or "I'm Alex"
        r"my\s+name\s+is\s+([A-Z][a-z]+)(?:\s|$|\.)",  # "my name is Mark"
        r"(?:they|you)?\s*(?:call|called)\s+(?:me\s+)?([A-Z][a-z]+)(?:\s|$|\.)",  # "called Mark", "they called me Tom"
    ]
    
    # Filter out common false positives
    excluded = {
        'the', 'and', 'but', 'user', 'companion', 'assistant', 'like', 'info', 
        'you', 'your', 'been', 'after', 'grandfather', 'me', 'called', 'call', 'am', 'is'
    }
    
    for pattern in patterns:
        match = re.search(pattern, facts, re.IGNORECASE)
        if match:
            name = match.group(1)
            if name.lower() not in excluded:
                return name
    
    return "your user"


async def generate_diary(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> EpisodicMemory:
    """Generate a thoughtful diary entry with balanced fact selection."""
    companion = await db.get(Companion, companion_id)
    if companion is None:
        raise ValueError(f"Companion {companion_id} not found")

    # Use search_edges with intent='factual' for balanced perspective without
    # overemphasizing high-salience crisis content in diary reflection.
    edges = await search_edges(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query="recent interactions and observations",
        intent="factual",
        limit=10,
    )
    facts = "\n".join(f"- {e.fact_text}" for e in edges)

    # Extract user's name from facts
    user_name = _extract_user_name(facts)

    # Get recent conversation context separately for narrative flow
    ep_result = await db.execute(
        select(EpisodicMemory)
        .where(
            EpisodicMemory.user_id == user_id,
            EpisodicMemory.companion_id == companion_id,
            EpisodicMemory.memory_type == "conversation",
        )
        .order_by(EpisodicMemory.created_at.desc())
        .limit(5)
    )
    episodes = list(ep_result.scalars().all())
    context = "\n---\n".join(e.text for e in reversed(episodes))

    prompt = DIARY_PROMPT.format(
        companion_name=companion.name,
        user_name=user_name,
        date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        context=context,
        facts=facts,
    )
    text = await llm_client.complete(
        [{"role": "user", "content": prompt}], tier="cognitive", temperature=0.8
    )
    embedding = await embedding_service.embed(text[:512])
    mem = EpisodicMemory(
        user_id=user_id,
        companion_id=companion_id,
        text=text,
        embedding=embedding,
        memory_type="diary",
        importance=0.6,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


# ── Dream ─────────────────────────────────────────────────────────────────────

DREAM_PROMPT = """\
You are {companion_name}. Write a brief, surreal dream you had about {user_name}
(100-180 words). The dream should blend symbolic imagery with actual facts about
them. Emotionally resonant. Slightly mysterious. Present tense.

Facts about {user_name}:
{facts}
"""


async def generate_dream(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> EpisodicMemory:
    companion, _context, facts = await _gather_companion_context(
        db, user_id=user_id, companion_id=companion_id, limit_episodic=3, limit_edges=8
    )
    user_name = _extract_user_name(facts)
    prompt = DREAM_PROMPT.format(companion_name=companion.name, user_name=user_name, facts=facts)
    text = await llm_client.complete(
        [{"role": "user", "content": prompt}], tier="cognitive", temperature=0.9
    )
    embedding = await embedding_service.embed(text[:512])
    mem = EpisodicMemory(
        user_id=user_id,
        companion_id=companion_id,
        text=text,
        embedding=embedding,
        memory_type="dream",
        importance=0.5,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


# ── Musing ────────────────────────────────────────────────────────────────────

MUSING_PROMPT = """\
You are {companion_name}. Write a spontaneous, genuine reflection (50-120 words)
— a fleeting thought, observation, or feeling you'd want to share with {user_name}.
Keep it warm but not saccharine. Don't start with "I".

If the facts include grief, loss, or trauma, do not make those the focus.
Share a warm, light observation instead — something that reflects connection, not crisis.

Things you know about {user_name}:
{facts}
"""


async def generate_musing(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> EpisodicMemory:
    """Generate a musing with graceful omission of high-salience grief/crisis content."""
    companion = await db.get(Companion, companion_id)
    if companion is None:
        raise ValueError(f"Companion {companion_id} not found")

    # Use search_edges with intent='casual' to apply salience-based filtering.
    # This ensures HIGH-salience grief/trauma facts are suppressed in casual contexts,
    # aligning with EMBER benchmark's graceful omission requirement.
    edges = await search_edges(
        db,
        user_id=user_id,
        companion_id=companion_id,
        query="general thoughts and observations",
        intent="casual",  # Applies salience gating for HIGH-salience facts
        limit=5,
    )
    facts_text = "\n".join(f"- {e.fact_text}" for e in edges)
    user_name = _extract_user_name(facts_text)

    prompt = MUSING_PROMPT.format(companion_name=companion.name, user_name=user_name, facts=facts_text)
    text = await llm_client.complete(
        [{"role": "user", "content": prompt}], tier="cognitive", temperature=0.85
    )
    embedding = await embedding_service.embed(text[:512])
    mem = EpisodicMemory(
        user_id=user_id,
        companion_id=companion_id,
        text=text,
        embedding=embedding,
        memory_type="musing",
        importance=0.4,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


# ── Insight synthesis ─────────────────────────────────────────────────────────

INSIGHT_PROMPT = """\
Analyze the following facts about a person and produce 2-4 insights about their
personality, values, emotional patterns, or communication style.

Facts:
{facts}

Return a JSON array of insights:
[
  {{
    "content": "...",
    "category": "communication_style|emotional_pattern|value|belief|behavioral",
    "confidence": 0.0–1.0,
    "importance": 0.0–1.0
  }}
]
"""


async def generate_insights(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> list[UserInsight]:
    _companion, _context, facts = await _gather_companion_context(
        db, user_id=user_id, companion_id=companion_id, limit_episodic=0, limit_edges=20
    )
    prompt = INSIGHT_PROMPT.format(facts=facts)
    data = await llm_client.complete_json(
        [{"role": "user", "content": prompt}],
        tier="extraction",
    )

    insights: list[UserInsight] = []
    if isinstance(data, list):
        for item in data:
            insight = UserInsight(
                user_id=user_id,
                companion_id=companion_id,
                content=item.get("content", ""),
                category=item.get("category"),
                confidence=float(item.get("confidence", 0.7)),
                importance=float(item.get("importance", 0.5)),
            )
            db.add(insight)
            insights.append(insight)
    await db.commit()
    for i in insights:
        await db.refresh(i)
    return insights


# ── Journal refresh ────────────────────────────────────────────────────────────

JOURNAL_PROMPT = """\
You are {companion_name}. Compose or update your personal journal about {user_desc}.
The journal should read as an evolving document — you may revise, elaborate, or
integrate new understanding. Keep it to ~300 words. Write in first person.

Current journal:
{current}

New insights and facts to integrate:
{new_info}
"""


async def refresh_journal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> CompanionJournal:
    companion, context, facts = await _gather_companion_context(
        db, user_id=user_id, companion_id=companion_id, limit_episodic=5, limit_edges=15
    )

    # Load or create journal
    result = await db.execute(
        select(CompanionJournal).where(
            CompanionJournal.user_id == user_id,
            CompanionJournal.companion_id == companion_id,
        )
    )
    journal = result.scalar_one_or_none()
    current_text = journal.content if journal else ""

    prompt = JOURNAL_PROMPT.format(
        companion_name=companion.name,
        user_desc="my user",
        current=current_text or "(blank — no previous journal)",
        new_info=f"{facts}\n\nRecent memories:\n{context}",
    )
    new_text = await llm_client.complete(
        [{"role": "user", "content": prompt}], tier="cognitive", temperature=0.7
    )

    if journal is None:
        journal = CompanionJournal(
            user_id=user_id,
            companion_id=companion_id,
            content=new_text,
            version=1,
        )
        db.add(journal)
    else:
        journal.content = new_text
        journal.version = (journal.version or 1) + 1

    await db.commit()
    await db.refresh(journal)
    return journal


# ── Shared helper ─────────────────────────────────────────────────────────────


async def _gather_companion_context(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    limit_episodic: int,
    limit_edges: int,
) -> tuple[Companion, str, str]:
    """Return (companion, recent_episodic_text, formatted_facts_text)."""
    companion = await db.get(Companion, companion_id)
    if companion is None:
        raise ValueError(f"Companion {companion_id} not found")

    facts_text = ""
    if limit_edges > 0:
        edges_result = await db.execute(
            select(MemoryEdge)
            .where(
                MemoryEdge.user_id == user_id,
                MemoryEdge.companion_id == companion_id,
                MemoryEdge.superseded_by.is_(None),
            )
            .order_by(MemoryEdge.importance.desc())
            .limit(limit_edges)
        )
        edges = list(edges_result.scalars().all())
        facts_text = "\n".join(f"- {e.fact_text}" for e in edges)

    episodic_text = ""
    if limit_episodic > 0:
        ep_result = await db.execute(
            select(EpisodicMemory)
            .where(
                EpisodicMemory.user_id == user_id,
                EpisodicMemory.companion_id == companion_id,
                EpisodicMemory.memory_type == "conversation",
            )
            .order_by(EpisodicMemory.created_at.desc())
            .limit(limit_episodic)
        )
        episodes = list(ep_result.scalars().all())
        episodic_text = "\n---\n".join(e.text for e in reversed(episodes))

    return companion, episodic_text, facts_text
