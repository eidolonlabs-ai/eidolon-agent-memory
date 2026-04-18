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
    """Search memory facts using hybrid semantic retrieval.

    intent: factual | emotional | casual | recall
    Use for: recalling facts to include in a response.
    Do NOT use: for open-ended listing or casual greetings.
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
    """Build a structured context block (facts + emotional + episodic) for prompt injection.

    Use for: preparing context before generating a response.
    Do NOT use: for single-fact lookup; use search_memory instead.
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
    """Look up a specific fact by subject and optional predicate.

    Use for: direct questions ('what is the user's job?').
    Do NOT use: for open-ended semantic search.
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
    """Get relationship state: trust score, closeness, milestones.

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
    limit: int = 5,
) -> str:
    """Search episodic memories (conversations, dreams, diaries, musings).

    memory_types: comma-separated e.g. 'conversation,diary' or empty for all.
    Use for: recalling past events or checking if topic was discussed.
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
            limit=limit,
        )
    return json.dumps(result)


@mcp.tool()
async def get_journal(api_key: str, companion_id: str) -> str:
    """Retrieve the companion's evolving journal about the user.

    Use for: loading personal context at session start.
    Do NOT use: on every message turn.
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
    """Store a new structured fact (subject→predicate→object).

    emotional_salience: HIGH (grief/trauma/major events) | MED (milestones) | LOW (routine).
    scope: user | shared (cross-companion visible) | companion (companion self-knowledge).
    Do NOT use: for storing AI inferences mid-conversation; use extract_session_facts post-session.
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
    """Store an episodic memory (conversation excerpt, reflection, etc.).

    memory_type: conversation | reflection | diary | dream | musing | narrative | insight_synthesis.
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
    """Update importance (and optionally confidence) of a fact.

    Use when the user confirms, corrects, or elevates a fact's significance.
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
    """Permanently delete a fact. Use only when user explicitly asks to forget.

    For corrections, prefer superseding (store a new fact) instead.
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
    """Set a user preference (key→value).

    companion_id: pass empty string for a global (cross-companion) preference.
    source: explicit (user said it) | extracted (inferred).
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
    """Generate a diary entry from the companion's perspective.

    Use for: daily scheduled reflection. Do NOT use mid-conversation.
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
    """Generate a surreal dream narrative about the user.

    Use for: morning check-in. Do NOT use more than once per day.
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
    """Generate a spontaneous thought or reflection from the companion.

    Use for: proactive outreach during idle time. Do NOT use inside an active response.
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
    """Analyse facts and generate psychological/behavioural insights.

    Do NOT use with fewer than 10 stored facts — quality will be poor.
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
    """Rebuild the companion's evolving journal about the user.

    Expensive — do NOT run on every session. Weekly or on major fact changes.
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
    """Extract and persist facts from a conversation segment using the LLM.

    conversation_text: full conversation as 'User: ...\\nAssistant: ...' format.
    Use for: post-session processing. Do NOT use on short (<3 turns) exchanges.
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
    """Create a new companion.

    personality_traits: comma-separated list e.g. 'empathetic,playful,curious'.
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
    """Get companion configuration details."""
    from eidolon_agent_memory.tools.companion import tool_get_companion
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_get_companion(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def list_companions(api_key: str) -> str:
    """List all companions for the authenticated user."""
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
    """Update mutable companion fields. Only provided (non-empty) fields change."""
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
    """Create or update a scheduled autonomous task.

    task_type: dream | diary | musing | insight | journal_refresh | decay | dedup | session_cleanup.
    schedule: cron expression e.g. '0 7 * * *' (7am daily).
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
    """List all scheduled tasks for a companion."""
    from eidolon_agent_memory.tools.scheduler import tool_list_task_schedules
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_list_task_schedules(
            db, user_id=user.id, companion_id=_uid(companion_id)
        )
    return json.dumps(result)


@mcp.tool()
async def toggle_task(api_key: str, task_id: str, enabled: bool) -> str:
    """Enable or disable a scheduled task without deleting it."""
    from eidolon_agent_memory.tools.scheduler import tool_toggle_task
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_toggle_task(
            db, user_id=user.id, task_id=_uid(task_id), enabled=enabled
        )
    return json.dumps(result)


@mcp.tool()
async def run_task_now(api_key: str, companion_id: str, task_type: str) -> str:
    """Immediately execute a cognitive task (one-shot).

    task_type: dream | diary | musing | insight | journal_refresh.
    Do NOT use for: decay | dedup | cleanup — those are schedule-only.
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
    """Return system info: version, fact counts, capabilities."""
    from eidolon_agent_memory.tools.utility import tool_info
    user = await _resolve_user(api_key)
    async with AsyncSessionLocal() as db:
        result = await tool_info(db, user_id=user.id)
    return json.dumps(result)


@mcp.tool()
async def provision_user(email: str = "", timezone: str = "UTC") -> str:
    """Create a new user and return their API key (shown once).

    No authentication required for this endpoint.
    """
    from eidolon_agent_memory.tools.utility import tool_provision_user
    async with AsyncSessionLocal() as db:
        result = await tool_provision_user(
            db, email=email or None, timezone=timezone
        )
    try:
        _API_KEY_USER_CACHE[result["api_key"]] = uuid.UUID(result["user_id"])
    except (KeyError, TypeError, ValueError):
        pass
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
