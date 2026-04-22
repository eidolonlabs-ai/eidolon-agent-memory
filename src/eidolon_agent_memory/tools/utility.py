"""
Utility tools: info, provision_user.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.core.auth import generate_api_key
from eidolon_agent_memory.models.memory import MemoryEdge, EpisodicMemory
from eidolon_agent_memory.models.user import User


async def tool_info(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Return system info: version, fact counts, episodic memory counts.

    Use for: health checks, diagnostics, capability discovery.
    """
    edge_count_result = await db.execute(
        select(func.count(MemoryEdge.id)).where(
            MemoryEdge.user_id == user_id,
            MemoryEdge.superseded_by.is_(None),
        )
    )
    edge_count = edge_count_result.scalar_one()

    episodic_count_result = await db.execute(
        select(func.count(EpisodicMemory.id)).where(
            EpisodicMemory.user_id == user_id
        )
    )
    episodic_count = episodic_count_result.scalar_one()

    return {
        "version": "0.1.0",
        "user_id": str(user_id),
        "active_facts": edge_count,
        "episodic_memories": episodic_count,
        "capabilities": [
            "memory_read",
            "memory_write",
            "cognitive_generation",
            "companion_management",
            "scheduler",
        ],
    }


async def tool_provision_user(
    db: AsyncSession,
    *,
    email: str | None = None,
    name: str | None = None,
    timezone: str = "UTC",
) -> dict[str, Any]:
    """
    Create a new user and return their raw API key (shown ONCE).

    Use for: onboarding flow; creating test accounts.
    The raw key is NOT stored — it cannot be retrieved later.
    """
    raw_key, hashed_key = generate_api_key()
    user = User(
        api_key_hash=hashed_key,
        email=email,
        name=name,
        timezone=timezone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "user_id": str(user.id),
        "api_key": raw_key,
        "warning": "Store this API key securely. It will not be shown again.",
    }


async def tool_update_user_name(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
) -> dict[str, Any]:
    """
    Update a user's name in the database.

    Use for: setting/updating the user's display name.
    """
    user = await db.get(User, user_id)
    if user is None:
        return {"error": f"User {user_id} not found"}
    
    user.name = name
    await db.commit()
    await db.refresh(user)
    return {
        "user_id": str(user.id),
        "name": user.name,
        "success": True,
    }


async def tool_get_user_info(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get user information including name, email, and timezone.

    Use for: checking current user state before updating.
    """
    user = await db.get(User, user_id)
    if user is None:
        return {"error": f"User {user_id} not found"}
    
    return {
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "timezone": user.timezone,
    }
