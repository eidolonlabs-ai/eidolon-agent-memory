"""
Companion management tools: create_companion, get_companion, list_companions,
update_companion.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.models.companion import Companion
from eidolon_agent_memory.services.relationship import get_or_create_relationship


async def tool_create_companion(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    persona: str | None = None,
    pronouns: str | None = None,
    personality_traits: list[str] | None = None,
    llm_config: dict | None = None,
) -> dict[str, Any]:
    """
    Create a new companion for the user.

    name must be unique per user.
    persona: short description of the companion's personality and role.
    personality_traits: list of trait strings e.g. ["empathetic", "playful"].
    llm_config: optional {"model": "...", "temperature": 0.8} overrides.
    """
    companion = Companion(
        user_id=user_id,
        name=name,
        persona=persona,
        pronouns=pronouns,
        personality_traits=personality_traits,
        llm_config=llm_config,
    )
    db.add(companion)
    await db.flush()
    # Initialise relationship record
    await get_or_create_relationship(
        db, user_id=user_id, companion_id=companion.id
    )
    await db.commit()
    await db.refresh(companion)
    return {
        "companion_id": str(companion.id),
        "name": companion.name,
        "created": True,
    }


async def tool_get_companion(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get companion details.

    Use for: loading companion configuration before a conversation.
    """
    result = await db.execute(
        select(Companion).where(
            Companion.id == companion_id, Companion.user_id == user_id
        )
    )
    companion = result.scalar_one_or_none()
    if companion is None:
        return {"error": "companion_not_found"}
    return {
        "companion_id": str(companion.id),
        "name": companion.name,
        "persona": companion.persona,
        "pronouns": companion.pronouns,
        "personality_traits": companion.personality_traits,
        "llm_config": companion.llm_config,
    }


async def tool_list_companions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """
    List all companions for the user.
    """
    result = await db.execute(
        select(Companion).where(Companion.user_id == user_id).order_by(Companion.name)
    )
    companions = list(result.scalars().all())
    return {
        "companions": [
            {"companion_id": str(c.id), "name": c.name, "pronouns": c.pronouns}
            for c in companions
        ],
        "count": len(companions),
    }


async def tool_update_companion(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    persona: str | None = None,
    pronouns: str | None = None,
    personality_traits: list[str] | None = None,
    llm_config: dict | None = None,
) -> dict[str, Any]:
    """
    Update mutable companion fields.

    Only provided (non-None) fields are changed.
    """
    result = await db.execute(
        select(Companion).where(
            Companion.id == companion_id, Companion.user_id == user_id
        )
    )
    companion = result.scalar_one_or_none()
    if companion is None:
        return {"error": "companion_not_found"}
    if persona is not None:
        companion.persona = persona
    if pronouns is not None:
        companion.pronouns = pronouns
    if personality_traits is not None:
        companion.personality_traits = personality_traits
    if llm_config is not None:
        companion.llm_config = {**(companion.llm_config or {}), **llm_config}
    await db.commit()
    return {"companion_id": str(companion.id), "updated": True}
