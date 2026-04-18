"""
Fact extraction service.

Extracts MemoryNodes + MemoryEdges from a conversation segment using the LLM.
Enforces validation rules that prevent low-quality / nonsensical facts.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from eidolon_agent_memory.services.llm import llm_client
from eidolon_agent_memory.services.memory import upsert_edge, upsert_node

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a precise memory extraction engine. Given a conversation segment, extract
structured facts about the USER and the COMPANION (assistant).

Priorities (in order):
1) Capture emotionally important facts first.
2) Preserve causal links (why/how/after/since/because relationships).
3) Capture identity shifts, loss events, and major transitions.
4) Capture companion-expressed values/preferences as shared memory.

You MUST explicitly look for and extract facts about:
- grief, loss, estrangement, trauma, and crisis
- identity or belief changes (e.g., faith loss, self-reframe, coming out)
- coping mechanisms and emotional anchors
- relationship dynamics and boundary violations
- ongoing conditions (anxiety, panic attacks, diagnosis, burnout)
- companion values and preferences stated in assistant messages

Return a JSON object with this exact schema:
{
  "nodes": [
    {
      "node_type": "entity|event|concept|emotion",
      "label": "human-readable label",
      "canonical_name": "lowercase_snake_case_name",
      "description": "optional short description"
    }
  ],
  "edges": [
    {
      "source_canonical": "canonical_name of source node",
      "target_canonical": "canonical_name of target node",
      "predicate": "VERB_PHRASE_IN_CAPS",
      "fact_text": "The user/companion <predicate in plain English> <target>.",
      "category": "personal|professional|relationship|health|interest|belief|goal|null",
      "reasoning_type": "explicit|deductive|inductive|abductive",
      "confidence": 0.0,
      "importance": 0.0,
      "temporal_type": "stable|ongoing|episodic",
      "emotional_context": "brief description or null",
      "emotional_salience": "HIGH|MED|LOW",
      "scope": "user|shared"
    }
  ]
}

Notes on scope:
- scope="user"   : fact is about the user
- scope="shared" : fact is about the companion (assistant) expressing values, preferences, or feelings

Validation rules:
- Reject any fact where the user IS_A an object (e.g. "User IS_A Cat").
- Reject facts with confidence < 0.25.
- emotional_salience=HIGH only for: grief, loss, trauma, major life transitions.
- emotional_salience=MED for: milestones, significant goals, meaningful relationships.
- emotional_salience=LOW for: routine preferences, trivial facts.
- Keep fact_text concise (max 120 characters).

Coverage rules:
- Do not only extract biographical trivia; include emotional and causal facts.
- If a message includes both an event and emotional meaning, extract both.
- Prefer specific predicates over vague HAS_FACT when possible.

CONVERSATION:
{conversation}
"""

SECOND_PASS_PROMPT = """\
You are reviewing a first-pass memory extraction for missed critical facts.

Task:
- Find meaningful facts missed in the first pass, with emphasis on HIGH and MED salience.
- Focus on emotional meaning, causal links, identity/belief shifts, and relationship dynamics.
- Return ONLY additive facts; do not repeat existing facts.

Return the same JSON schema with "nodes" and "edges".

CONVERSATION:
{conversation}

FIRST_PASS_JSON:
{first_pass_json}
"""


def _merge_extractions(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    primary_nodes = primary.get("nodes", []) if isinstance(primary.get("nodes", []), list) else []
    primary_edges = primary.get("edges", []) if isinstance(primary.get("edges", []), list) else []
    secondary_nodes = secondary.get("nodes", []) if isinstance(secondary.get("nodes", []), list) else []
    secondary_edges = secondary.get("edges", []) if isinstance(secondary.get("edges", []), list) else []

    nodes_by_canonical: dict[str, dict[str, Any]] = {}
    merged_nodes: list[dict[str, Any]] = []

    for node in primary_nodes + secondary_nodes:
        if not isinstance(node, dict):
            continue
        canonical = node.get("canonical_name")
        if not canonical or not isinstance(canonical, str):
            continue
        if canonical in nodes_by_canonical:
            continue
        nodes_by_canonical[canonical] = node
        merged_nodes.append(node)

    seen_edges: set[tuple[str, str, str, str]] = set()
    merged_edges: list[dict[str, Any]] = []
    for edge in primary_edges + secondary_edges:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("source_canonical", "")).strip()
        tgt = str(edge.get("target_canonical", "")).strip()
        pred = str(edge.get("predicate", "")).strip().upper()
        fact = str(edge.get("fact_text", "")).strip().lower()
        if not src or not tgt or not pred or not fact:
            continue
        key = (src, tgt, pred, fact)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        merged_edges.append(edge)

    return {"nodes": merged_nodes, "edges": merged_edges}


async def extract_facts(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    conversation_text: str,
    source_session_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """
    Run LLM extraction on *conversation_text* and persist nodes+edges.
    Returns {"nodes": N, "edges": N} created/updated counts.
    """
    prompt = EXTRACTION_PROMPT.replace("{conversation}", conversation_text)
    try:
        first_pass: Any = await llm_client.complete_json(
            [{"role": "user", "content": prompt}],
            tier="extraction",
        )
    except Exception as exc:
        logger.error("LLM extraction failed: %s", exc)
        return {"nodes": 0, "edges": 0}

    data: dict[str, Any] = dict(first_pass) if isinstance(first_pass, dict) else {"nodes": [], "edges": []}
    first_edges = data.get("edges", []) if isinstance(data.get("edges", []), list) else []
    high_or_med = 0
    for edge in first_edges:
        if not isinstance(edge, dict):
            continue
        salience = str(edge.get("emotional_salience", "LOW")).upper()
        if salience in {"HIGH", "MED"}:
            high_or_med += 1

    # Adaptive second pass: only run when first pass coverage looks thin.
    should_run_second_pass = len(first_edges) < 8 or high_or_med < 2
    if should_run_second_pass:
        try:
            second_prompt = (
                SECOND_PASS_PROMPT
                .replace("{conversation}", conversation_text)
                .replace("{first_pass_json}", json.dumps(data, ensure_ascii=True))
            )
            second_pass: Any = await llm_client.complete_json(
                [{"role": "user", "content": second_prompt}],
                tier="extraction",
            )
            if isinstance(second_pass, dict):
                data = _merge_extractions(data, second_pass)
        except Exception as exc:
            logger.warning("Second-pass extraction failed, continuing with first pass: %s", exc)

    nodes_raw: list[dict] = data.get("nodes", [])
    edges_raw: list[dict] = data.get("edges", [])

    # Build a map canonical_name → MemoryNode
    node_map: dict[str, Any] = {}
    nodes_count = 0
    for n in nodes_raw:
        try:
            node = await upsert_node(
                db,
                user_id=user_id,
                companion_id=companion_id,
                node_type=n.get("node_type", "entity"),
                label=n["label"],
                canonical_name=n["canonical_name"],
                description=n.get("description"),
                embed=False,
            )
            node_map[n["canonical_name"]] = node
            nodes_count += 1
        except (KeyError, Exception):
            continue

    edges_count = 0
    for e in edges_raw:
        try:
            # Validation: reject IS_A category nonsense
            if e.get("predicate", "").upper() == "IS_A":
                continue
            if float(e.get("confidence", 0)) < 0.25:
                continue

            src = node_map.get(e["source_canonical"])
            tgt = node_map.get(e["target_canonical"])
            if src is None or tgt is None:
                continue

            await upsert_edge(
                db,
                user_id=user_id,
                companion_id=companion_id,
                source_node_id=src.id,
                target_node_id=tgt.id,
                predicate=e["predicate"].upper(),
                fact_text=e["fact_text"],
                category=e.get("category"),
                reasoning_type=e.get("reasoning_type", "explicit"),
                confidence=float(e.get("confidence", 1.0)),
                importance=float(e.get("importance", 0.5)),
                temporal_type=e.get("temporal_type", "stable"),
                emotional_context=e.get("emotional_context"),
                emotional_salience=e.get("emotional_salience", "LOW"),
                scope=e.get("scope", "user"),
                source="chat",
                source_session_id=source_session_id,
            )
            edges_count += 1
        except (KeyError, Exception):
            continue

    await db.commit()
    return {"nodes": nodes_count, "edges": edges_count}
