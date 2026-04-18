"""
Relationship tracking helpers.
Updates trust/closeness scores after interactions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.relationship import Relationship


async def get_or_create_relationship(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> Relationship:
    result = await db.execute(
        select(Relationship).where(
            Relationship.user_id == user_id,
            Relationship.companion_id == companion_id,
        )
    )
    rel = result.scalar_one_or_none()
    if rel is None:
        rel = Relationship(user_id=user_id, companion_id=companion_id)
        db.add(rel)
        await db.flush()
    return rel


async def record_interaction(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    user_message_count: int = 1,
) -> Relationship:
    """
    Increment interaction counters and nudge closeness upward.
    Trust grows more slowly (requires milestone events).
    """
    rel = await get_or_create_relationship(
        db, user_id=user_id, companion_id=companion_id
    )
    now = datetime.now(timezone.utc)

    if rel.first_interaction_at is None:
        rel.first_interaction_at = now
    rel.last_interaction_at = now
    rel.interaction_count = (rel.interaction_count or 0) + 1
    rel.total_user_messages = (rel.total_user_messages or 0) + user_message_count
    rel.absence_streak_days = 0

    # Closeness: logarithmic growth, capped at 1.0
    # Each interaction adds ~0.002 (reaches ~0.8 after ~300 interactions)
    delta = 0.002 / (1.0 + (rel.closeness_score or 0.1) * 5)
    rel.closeness_score = min(1.0, (rel.closeness_score or 0.1) + delta)

    await db.flush()
    return rel


async def record_absence(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    days_elapsed: int,
) -> Relationship:
    """Increment absence streak and decay closeness slightly."""
    rel = await get_or_create_relationship(
        db, user_id=user_id, companion_id=companion_id
    )
    rel.absence_streak_days = (rel.absence_streak_days or 0) + days_elapsed
    # Mild closeness decay per day of absence
    decay = 0.001 * days_elapsed
    rel.closeness_score = max(0.05, (rel.closeness_score or 0.1) - decay)
    await db.flush()
    return rel
