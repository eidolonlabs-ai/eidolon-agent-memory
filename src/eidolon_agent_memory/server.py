"""
Eidolon Agent Memory MCP server.

Registers all 27 tools + 3 resources.
Supports both stdio (default for MCP clients) and HTTP/SSE (for web integrations).
"""
from __future__ import annotations

import json
import logging
import uuid

from mcp.server.fastmcp import FastMCP

from eidolon_agent_memory.core.auth import verify_api_key
from eidolon_agent_memory.core.config import settings
from eidolon_agent_memory.db.session import AsyncSessionLocal
from eidolon_agent_memory.models.user import User
from sqlalchemy import select

log = logging.getLogger(__name__)

# Fast path for repeated authenticated calls in benchmark loops.
_API_KEY_USER_CACHE: dict[str, uuid.UUID] = {}

mcp = FastMCP(
    name="eidolon-agent-memory",
    instructions=(
        "Cognitive companion memory platform. "
        "Stores, retrieves, and reasons about facts, relationships, and episodic memories."
    ),
)

# ── Auth helper ───────────────────────────────────────────────────────────────


async def _resolve_user(api_key: str) -> User:
    """Verify API key and return the User row. Raises ValueError on failure."""
    cached_user_id = _API_KEY_USER_CACHE.get(api_key)
    if cached_user_id is not None:
        async with AsyncSessionLocal() as db:
            cached = await db.execute(select(User).where(User.id == cached_user_id))
            cached_user = cached.scalar_one_or_none()
            if cached_user is not None:
                return cached_user

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = list(result.scalars().all())
    for user in users:
        if verify_api_key(api_key, user.api_key_hash):
            _API_KEY_USER_CACHE[api_key] = user.id
            return user
    raise ValueError("Invalid API key")


# ── Tool registration helpers ─────────────────────────────────────────────────


def _uid(val: str) -> uuid.UUID:
    return uuid.UUID(val)


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY READ TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_memory(
    api_key: str,
    companion_id: str,
    query: str,
    intent: str = "factual",
    limit: int = 10,
) -> str:
    """Search structured memory facts with hybrid semantic retrieval.

    Auth: requires api_key.
    Inputs: companion_id, query, intent (factual|emotional|casual|recall), limit.
    intent semantics:
      casual   — suppress HIGH-salience grief/trauma facts; use when writing lighthearted or fun messages.
      emotional — boost HIGH-salience facts; use when user is discussing difficult emotions.
      recall   — emphasise recency; use when user asks what has happened lately.
      factual  — balanced default; use for most informational lookups.
    Returns: JSON {"facts": [{"id": uuid, "fact_text": str, "predicate": str, "emotional_salience": HIGH|MED|LOW, "importance": float, "confidence": float, "scope": user|shared|companion, "score": float}], "count": int}
    Side effects: none.
    Use for: recalling facts to include in a response.
    Do not use: open-ended listing or casual greetings.
    """
    from eidolon_agent_memory.tools.memory_read import tool_search_memory
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_search_memory(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            query=query,
            intent=intent,
            limit=limit,
        )
    return json.dumps(result)


@mcp.tool()
async def get_context(
    api_key: str,
    companion_id: str,
    query: str,
    intent: str = "factual",
) -> str:
    """Build a structured context block from facts and episodic memory.

    Auth: requires api_key.
    Inputs: companion_id, query, intent (factual|emotional|casual|recall).
    intent semantics:
      casual   — suppress HIGH-salience grief/trauma facts and crisis-laden diary/dream entries.
                 Use when composing lighthearted, fun, or casual messages to the user.
      emotional — surface and highlight HIGH-salience facts; use when the user is processing
                  difficult emotions or explicitly discussing sensitive topics.
      recall   — emphasise recency; use for "what's been happening lately" queries.
      factual  — balanced default for most response generation.
    Returns: JSON {"context": str (formatted text), "fact_count": int}
    Side effects: none.
    Use for: preparing context before generating a response.
    Do not use: single-fact lookup; use lookup_fact or search_memory.
    """
    from eidolon_agent_memory.tools.memory_read import tool_get_context
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_context(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            query=query,
            intent=intent,
        )
    return json.dumps(result)


@mcp.tool()
async def lookup_fact(
    api_key: str,
    companion_id: str,
    subject: str,
    predicate: str = "",
) -> str:
    """Look up facts by subject and optional predicate.

    Auth: requires api_key.
    Inputs: companion_id, subject, optional predicate.
    Returns: JSON {"facts": [{"id": uuid, "fact_text": str, "predicate": str, "importance": float, "confidence": float, "emotional_salience": HIGH|MED|LOW}]}
    Side effects: none.
    Use for: direct fact questions.
    Do not use: broad semantic exploration.
    """
    from eidolon_agent_memory.tools.memory_read import tool_lookup_fact
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_lookup_fact(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            subject=subject,
            predicate=predicate or None,
        )
    return json.dumps(result)


@mcp.tool()
async def get_relationship(api_key: str, companion_id: str) -> str:
    """Get relationship state for the current user and companion.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"trust": float, "closeness": float, "interactions": int, "absence_streak_days": int, "milestones": [str]}
    Side effects: none.
    Use for: calibrating tone and intimacy in responses.
    """
    from eidolon_agent_memory.tools.memory_read import tool_get_relationship
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_relationship(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def get_episodic(
    api_key: str,
    companion_id: str,
    query: str,
    memory_types: str = "",
    intent: str = "factual",
    limit: int = 5,
) -> str:
    """Search episodic memories using semantic retrieval.

    Auth: requires api_key.
    Inputs: companion_id, query, optional memory_types CSV, intent (factual|emotional|casual|recall), limit.
    intent semantics:
      casual   — suppress diary/dream entries unlikely to be relevant; use for casual/fun queries.
      emotional — surface all content including crisis memories; use when processing difficult emotions.
      factual  — balanced default.
    Returns: JSON {"memories": [{"id": uuid, "text": str, "memory_type": conversation|reflection|diary|dream|musing|narrative|insight_synthesis, "importance": float, "score": float}]}
    Side effects: none.
    Use for: recalling past events or whether a topic was discussed.
    """
    from eidolon_agent_memory.tools.memory_read import tool_get_episodic
    user = await _resolve_user(api_key)
    types = [t.strip() for t in memory_types.split(",") if t.strip()] or None
    async with AsyncSessionLocal() as db:
        result = await tool_get_episodic(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            query=query,
            memory_types=types,
            intent=intent,
            limit=limit,
        )
    return json.dumps(result)


@mcp.tool()
async def get_journal(api_key: str, companion_id: str) -> str:
    """Retrieve the current companion journal for this user.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"journal": str, "version": int, "top_insights": [{"content": str, "category": str}], "preferences": {str: str}}
    Side effects: none.
    Use for: loading personal context at session start.
    Do not use: every message turn.
    """
    from eidolon_agent_memory.tools.memory_read import tool_get_journal
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_journal(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY WRITE TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def store_fact(
    api_key: str,
    companion_id: str,
    subject: str,
    predicate: str,
    obj: str,
    fact_text: str,
    category: str = "",
    confidence: float = 1.0,
    importance: float = 0.5,
    emotional_salience: str = "LOW",
    emotional_context: str = "",
    scope: str = "user",
    created_at: str = "",
    updated_at: str = "",
) -> str:
    """Store a structured fact as subject, predicate, object, and fact_text.

    Auth: requires api_key.
    Inputs: companion_id plus fact fields and optional metadata.
    Returns: JSON {"edge_id": uuid, "stored": true}
    Side effects: writes memory nodes and edges.
    Constraints: emotional_salience is HIGH|MED|LOW, scope is user|shared|companion.
    Do not use: storing speculative AI inferences mid-conversation.
    """
    from eidolon_agent_memory.tools.memory_write import tool_store_fact
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_store_fact(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            subject=subject,
            predicate=predicate,
            obj=obj,
            fact_text=fact_text,
            category=category or None,
            confidence=confidence,
            importance=importance,
            emotional_salience=emotional_salience,
            emotional_context=emotional_context or None,
            scope=scope,
            created_at=created_at or None,
            updated_at=updated_at or None,
        )
    return json.dumps(result)


@mcp.tool()
async def store_episodic(
    api_key: str,
    companion_id: str,
    text: str,
    memory_type: str = "conversation",
    importance: float = 0.5,
    session_id: str = "",
) -> str:
    """Store one episodic memory entry.

    Auth: requires api_key.
    Inputs: companion_id, text, memory_type, importance, optional session_id.
    Returns: JSON {"memory_id": uuid, "stored": true}
    Side effects: writes episodic memory row.
    """
    from eidolon_agent_memory.tools.memory_write import tool_store_episodic
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_store_episodic(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            text=text,
            memory_type=memory_type,
            importance=importance,
            session_id=_uid(session_id) if session_id else None,
        )
    return json.dumps(result)


@mcp.tool()
async def update_fact_importance(
    api_key: str,
    edge_id: str,
    importance: float,
    confidence: float = -1.0,
) -> str:
    """Update a fact's importance and optional confidence.

    Auth: requires api_key.
    Inputs: edge_id, importance, optional confidence.
    Returns: JSON {"updated": bool (true if fact found and updated, false otherwise)}
    Side effects: updates existing fact row.
    Use for: explicit user correction or reprioritization.
    """
    from eidolon_agent_memory.tools.memory_write import tool_update_fact_importance
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_update_fact_importance(
            db,
            user_id=user.id,
            edge_id=_uid(edge_id),
            importance=importance,
            confidence=confidence if confidence >= 0 else None,
        )
    return json.dumps(result)


@mcp.tool()
async def delete_fact(api_key: str, edge_id: str) -> str:
    """Permanently delete a fact edge.

    Auth: requires api_key.
    Inputs: edge_id.
    Returns: JSON {"deleted": bool (true if fact found and deleted, false otherwise)}
    Side effects: destructive write.
    Use only when user explicitly asks to forget.
    """
    from eidolon_agent_memory.tools.memory_write import tool_delete_fact
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_delete_fact(
            db, user_id=user.id, edge_id=_uid(edge_id)
        )
    return json.dumps(result)


@mcp.tool()
async def set_preference(
    api_key: str,
    companion_id: str,
    key: str,
    value: str,
    source: str = "explicit",
) -> str:
    """Set or update a user preference key and value.

    Auth: requires api_key.
    Inputs: companion_id, key, value, source.
    Returns: JSON {"key": str, "value": str, "stored": true}
    Side effects: writes preference row.
    Notes: empty companion_id stores a global preference.
    """
    from eidolon_agent_memory.tools.memory_write import tool_set_preference
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_set_preference(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id) if companion_id else None,
            key=key,
            value=value,
            source=source,
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# COGNITIVE TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def generate_diary(api_key: str, companion_id: str) -> str:
    """Generate a diary memory from the companion perspective.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"memory_id": uuid, "memory_type": "diary", "text": str (full diary entry)}
    Side effects: writes episodic memory.
    Use for: scheduled reflection, not mid-conversation.
    Cost: LLM generation; run periodically.
    """
    from eidolon_agent_memory.tools.cognitive import tool_generate_diary
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_generate_diary(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def generate_dream(api_key: str, companion_id: str) -> str:
    """Generate a dream-style episodic narrative about the user.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"memory_id": uuid, "memory_type": "dream", "text": str (surreal narrative)}
    Side effects: writes episodic memory.
    Use for: occasional proactive content.
    Cost: LLM generation; run as autonomous task.
    """
    from eidolon_agent_memory.tools.cognitive import tool_generate_dream
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_generate_dream(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def generate_musing(api_key: str, companion_id: str) -> str:
    """Generate a short spontaneous reflection.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"memory_id": uuid, "memory_type": "musing", "text": str (short thought)}
    Side effects: writes episodic memory.
    Use for: idle-time outreach, not inside active response generation.
    Cost: LLM generation; run asynchronously.
    """
    from eidolon_agent_memory.tools.cognitive import tool_generate_musing
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_generate_musing(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def generate_insights(api_key: str, companion_id: str) -> str:
    """Generate synthesized insights from stored facts.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"insights": [{"id": uuid, "content": str (psychological insight), "category": str, "confidence": float}], "count": int}
    Side effects: writes user_insight rows.
    Do not use with very sparse fact history.
    Cost: LLM analysis; run periodically.
    """
    from eidolon_agent_memory.tools.cognitive import tool_generate_insights
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_generate_insights(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def refresh_journal(api_key: str, companion_id: str) -> str:
    """Rebuild the evolving companion journal for this user.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"journal_id": uuid, "version": int, "length": int (character count)}
    Side effects: writes or updates journal.
    Cost: expensive (LLM synthesis); run periodically or after major memory changes.
    """
    from eidolon_agent_memory.tools.cognitive import tool_refresh_journal
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_refresh_journal(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def extract_session_facts(
    api_key: str,
    companion_id: str,
    conversation_text: str,
    session_id: str = "",
) -> str:
    """Extract and persist structured facts from conversation text.

    Auth: requires api_key.
    Inputs: companion_id, conversation_text, optional session_id.
    Returns: JSON with extraction counts (structure varies by service implementation).
    Side effects: writes nodes, edges, and related memory rows.
    Use for: post-session ingestion of meaningful exchanges.
    Cost: LLM extraction and embeddings; run after sessions end.
    """
    from eidolon_agent_memory.tools.cognitive import tool_extract_session_facts
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_extract_session_facts(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            conversation_text=conversation_text,
            session_id=_uid(session_id) if session_id else None,
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPANION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def create_companion(
    api_key: str,
    name: str,
    persona: str = "",
    pronouns: str = "",
    personality_traits: str = "",
) -> str:
    """Create a new companion profile for the authenticated user.

    Auth: requires api_key.
    Inputs: name, optional persona, pronouns, personality_traits CSV.
    Returns: JSON {"companion_id": uuid, "name": str, "created": true}
    Side effects: writes companion row and initializes relationship state.
    """
    from eidolon_agent_memory.tools.companion import tool_create_companion
    user = await _resolve_user(api_key)
    traits = [t.strip() for t in personality_traits.split(",") if t.strip()] or None
    async with AsyncSessionLocal() as db:
        result = await tool_create_companion(
            db,
            user_id=user.id,
            name=name,
            persona=persona or None,
            pronouns=pronouns or None,
            personality_traits=traits,
        )
    return json.dumps(result)


@mcp.tool()
async def get_companion(api_key: str, companion_id: str) -> str:
    """Get companion configuration details.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"companion_id": uuid, "name": str, "persona": str|null, "pronouns": str|null, "personality_traits": [str]|null, "llm_config": dict|null} or {"error": "companion_not_found"}
    Side effects: none.
    """
    from eidolon_agent_memory.tools.companion import tool_get_companion
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_companion(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def list_companions(api_key: str) -> str:
    """List all companions for the authenticated user.

    Auth: requires api_key.
    Inputs: none beyond api_key.
    Returns: JSON {"companions": [{"companion_id": uuid, "name": str, "pronouns": str|null}], "count": int}
    Side effects: none.
    """
    from eidolon_agent_memory.tools.companion import tool_list_companions
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_list_companions(db, user_id=user.id)
    return json.dumps(result)


@mcp.tool()
async def update_companion(
    api_key: str,
    companion_id: str,
    persona: str = "",
    pronouns: str = "",
    personality_traits: str = "",
) -> str:
    """Update mutable companion fields.

    Auth: requires api_key.
    Inputs: companion_id plus optional persona, pronouns, personality_traits CSV.
    Returns: JSON {"companion_id": uuid, "updated": true} or {"error": "companion_not_found"}
    Side effects: updates companion profile row.
    """
    from eidolon_agent_memory.tools.companion import tool_update_companion
    user = await _resolve_user(api_key)
    traits = (
        [t.strip() for t in personality_traits.split(",") if t.strip()]
        if personality_traits
        else None
    )
    async with AsyncSessionLocal() as db:
        result = await tool_update_companion(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            persona=persona or None,
            pronouns=pronouns or None,
            personality_traits=traits,
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def set_task_schedule(
    api_key: str,
    companion_id: str,
    task_type: str,
    schedule: str,
    timezone: str = "UTC",
) -> str:
    """Create or update an autonomous scheduled task.

    Auth: requires api_key.
    Inputs: companion_id, task_type (dream|diary|musing|insight|journal_refresh), cron schedule, timezone.
    Returns: JSON {"task_id": uuid, "task_type": str, "schedule": str (cron), "timezone": str, "enabled": true} or {"error": "Unknown task_type"}
    Side effects: writes or updates scheduled task row.
    """
    from eidolon_agent_memory.tools.scheduler import tool_set_task_schedule
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_set_task_schedule(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            task_type=task_type,
            schedule=schedule,
            timezone=timezone,
        )
    return json.dumps(result)


@mcp.tool()
async def list_task_schedules(api_key: str, companion_id: str) -> str:
    """List all scheduled tasks for one companion.

    Auth: requires api_key.
    Inputs: companion_id.
    Returns: JSON {"tasks": [{"task_id": uuid, "task_type": str, "schedule": str (cron), "timezone": str, "enabled": bool, "last_run_at": datetime|null}], "count": int}
    Side effects: none.
    """
    from eidolon_agent_memory.tools.scheduler import tool_list_task_schedules
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_list_task_schedules(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def toggle_task(api_key: str, task_id: str, enabled: bool) -> str:
    """Enable or disable a scheduled task.

    Auth: requires api_key.
    Inputs: task_id, enabled flag.
    Returns: JSON {"task_id": uuid, "enabled": bool} or {"error": "task_not_found"}
    Side effects: updates scheduled task row.
    """
    from eidolon_agent_memory.tools.scheduler import tool_toggle_task
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_toggle_task(
            db, user_id=user.id, task_id=_uid(task_id), enabled=enabled
        )
    return json.dumps(result)


@mcp.tool()
async def run_task_now(api_key: str, companion_id: str, task_type: str) -> str:
    """Immediately execute a one-shot cognitive task.

    Auth: requires api_key.
    Inputs: companion_id, task_type (diary|dream|musing|insight|journal_refresh).
    Returns: JSON {"task_type": str, "memory_id": uuid, "text": str} or {"task_type": str, "count": int} or {"task_type": str, "journal_id": uuid, "version": int} or {"error": str}
    Side effects: writes memories, insights, or journal updates depending on task.
    Do not use for maintenance tasks like decay or dedup.
    Cost: LLM generation per task type.
    """
    from eidolon_agent_memory.tools.scheduler import tool_run_task_now
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_run_task_now(
            db,
            user_id=user.id,
            companion_id=_uid(companion_id),
            task_type=task_type,
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def info(api_key: str) -> str:
    """Return diagnostic system info for the authenticated user.

    Auth: requires api_key.
    Inputs: none beyond api_key.
    Returns: JSON {"version": str, "user_id": uuid, "active_facts": int, "episodic_memories": int, "capabilities": [str]}
    Side effects: none.
    """
    from eidolon_agent_memory.tools.utility import tool_info
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_info(db, user_id=user.id)
    return json.dumps(result)


@mcp.tool()
async def provision_user(email: str = "", name: str = "", timezone: str = "UTC") -> str:
    """Provision a new user and return a one-time raw API key.

    Auth: none.
    Inputs: optional email, name, and timezone.
    Returns: JSON {"user_id": uuid, "api_key": str (shown once; store securely), "warning": "Store this API key securely. It will not be shown again."}
    Side effects: writes user row and authentication material.
    Note: API key is not retrievable after this call.
    """
    from eidolon_agent_memory.tools.utility import tool_provision_user
    async with AsyncSessionLocal() as db:
        result = await tool_provision_user(
            db, email=email or None, name=name or None, timezone=timezone
        )
    try:
        _API_KEY_USER_CACHE[result["api_key"]] = uuid.UUID(result["user_id"])
    except (KeyError, TypeError, ValueError):
        pass
    return json.dumps(result)


@mcp.tool()
async def update_user_name(api_key: str, name: str) -> str:
    """Update the authenticated user's name.

    Auth: requires api_key.
    Inputs: name (string).
    Returns: JSON {"user_id": uuid, "name": str, "success": true}
    Side effects: updates user row.
    Use for: setting or updating the user's display name.
    """
    from eidolon_agent_memory.tools.utility import tool_update_user_name
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_update_user_name(db, user_id=user.id, name=name)
    return json.dumps(result)


@mcp.tool()
async def get_user_info(api_key: str) -> str:
    """Get authenticated user's profile information.

    Auth: requires api_key.
    Inputs: none.
    Returns: JSON {"user_id": uuid, "name": str|null, "email": str|null, "timezone": str}
    Side effects: none (read-only).
    Use for: checking current user state before updating name or other profile info.
    """
    from eidolon_agent_memory.tools.utility import tool_get_user_info
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_user_info(db, user_id=user.id)
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCES
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.resource("eidolon_agent_memory://user/{api_key}/companions")
async def resource_companions(api_key: str) -> str:
    """List all companions for the authenticated user."""
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        from eidolon_agent_memory.tools.companion import tool_list_companions
        result = await tool_list_companions(db, user_id=user.id)
    return json.dumps(result)


@mcp.resource("eidolon_agent_memory://companion/{api_key}/{companion_id}/journal")
async def resource_journal(api_key: str, companion_id: str) -> str:
    """Current companion journal."""
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        from eidolon_agent_memory.tools.memory_read import tool_get_journal
        result = await tool_get_journal(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.resource("eidolon_agent_memory://companion/{api_key}/{companion_id}/relationship")
async def resource_relationship(api_key: str, companion_id: str) -> str:
    """Current relationship state."""
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        from eidolon_agent_memory.tools.memory_read import tool_get_relationship
        result = await tool_get_relationship(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    transport = settings.mcp_transport.lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = settings.mcp_host
        mcp.settings.port = settings.mcp_port
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
