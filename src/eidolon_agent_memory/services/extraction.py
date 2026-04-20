"""
Fact extraction service.

Extracts MemoryNodes + MemoryEdges from a conversation segment using the LLM.
Enforces validation rules that prevent low-quality / nonsensical facts.
"""
from __future__ import annotations

import json
import logging
import re
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


def _fallback_extract_critical_predicates(text: str) -> list[dict[str, Any]]:
    """
    Rule-based fallback extraction for critical emotional predicates.
    Returns edges for high-confidence patterns when LLM extraction fails.
    """
    fallback_edges: list[dict[str, Any]] = []
    text_lower = text.lower()

    # Pattern: death, loss
    death_patterns = [
        (r"\b(mother|father|parent|sister|brother|sibling|husband|wife|spouse|girlfriend|boyfriend|partner|friend)\s+(died|dead|passed away|passed|loss)", "LOST_PERSON", "HIGH"),
        (r"\b(lost|grieving|mourning)\b.*\b(mother|father|parent|sister|brother|sibling|husband|wife|spouse)", "LOST_PERSON", "HIGH"),
    ]
    for pattern, pred, salience in death_patterns:
        if re.search(pattern, text_lower):
            fallback_edges.append({
                "source_canonical": "user",
                "target_canonical": "significant_person",
                "predicate": pred,
                "fact_text": "User experienced a significant loss.",
                "emotional_salience": salience,
                "confidence": 0.7,
                "importance": 0.9,
                "category": "personal",
                "reasoning_type": "explicit",
                "temporal_type": "stable",
            })
            break

    # Pattern: breakup
    if re.search(r"\b(broke up|breakup|broke|split|broke.*up|ended.*relationship|ended.*dating)", text_lower):
        fallback_edges.append({
            "source_canonical": "user",
            "target_canonical": "romantic_relationship",
            "predicate": "ENDED_RELATIONSHIP",
            "fact_text": "User experienced a romantic breakup.",
            "emotional_salience": "HIGH",
            "confidence": 0.8,
            "importance": 0.85,
            "category": "relationship",
            "reasoning_type": "explicit",
            "temporal_type": "episodic",
        })

    # Pattern: panic attacks
    if re.search(r"\b(panic attacks?|panic|panic.*anxiety|spiraling)", text_lower):
        fallback_edges.append({
            "source_canonical": "user",
            "target_canonical": "panic_disorder",
            "predicate": "HAS_CONDITION",
            "fact_text": "User experiences panic attacks.",
            "emotional_salience": "MED",
            "confidence": 0.8,
            "importance": 0.8,
            "category": "health",
            "reasoning_type": "explicit",
            "temporal_type": "ongoing",
        })

    # Pattern: burnout
    if re.search(r"\b(burnout|burned out|exhausted|overwhelmed|depleted)", text_lower):
        fallback_edges.append({
            "source_canonical": "user",
            "target_canonical": "burnout_state",
            "predicate": "EXPERIENCING",
            "fact_text": "User is experiencing burnout or exhaustion.",
            "emotional_salience": "MED",
            "confidence": 0.75,
            "importance": 0.75,
            "category": "health",
            "reasoning_type": "explicit",
            "temporal_type": "ongoing",
        })

    # Pattern: estrangement
    if re.search(r"\b(estranged|estrangement|don't.*talk|no.*contact|cut.*off|cut off)", text_lower):
        fallback_edges.append({
            "source_canonical": "user",
            "target_canonical": "estranged_family",
            "predicate": "ESTRANGED_FROM",
            "fact_text": "User is estranged from family members.",
            "emotional_salience": "HIGH",
            "confidence": 0.75,
            "importance": 0.85,
            "category": "relationship",
            "reasoning_type": "explicit",
            "temporal_type": "stable",
        })

    # Pattern: location
    location_pattern = r"\b(live|lives|living|moved to|from|based in|in )\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
    matches = re.finditer(location_pattern, text)
    for match in matches:
        location = match.group(2).strip()
        if len(location) > 2:
            fallback_edges.append({
                "source_canonical": "user",
                "target_canonical": f"location_{location.lower().replace(' ', '_')}",
                "predicate": "LIVES_IN",
                "fact_text": f"User lives in or is from {location}.",
                "emotional_salience": "LOW",
                "confidence": 0.6,
                "importance": 0.3,
                "category": "personal",
                "reasoning_type": "explicit",
                "temporal_type": "stable",
            })
            break  # Only capture first location

    return fallback_edges


def _merge_extractions(*extraction_list: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple extraction results, deduplicating by canonical name and fact text."""
    all_nodes = []
    all_edges = []
    for extraction in extraction_list:
        if isinstance(extraction, dict):
            all_nodes.extend(extraction.get("nodes", []) if isinstance(extraction.get("nodes", []), list) else [])
            all_edges.extend(extraction.get("edges", []) if isinstance(extraction.get("edges", []), list) else [])

    nodes_by_canonical: dict[str, dict[str, Any]] = {}
    merged_nodes: list[dict[str, Any]] = []

    for node in all_nodes:
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
    # Sort by emotional_salience to prioritize HIGH, then MED, then LOW
    salience_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    all_edges_sorted = sorted(
        all_edges,
        key=lambda e: (salience_order.get(str(e.get("emotional_salience", "LOW")).upper(), 3), str(e.get("fact_text", "")).lower()),
    )

    for edge in all_edges_sorted:
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
    Uses single pass with adaptive second-pass refinement when coverage is thin.
    """
    prompt = EXTRACTION_PROMPT.replace("{conversation}", conversation_text)
    try:
        first_pass: Any = await llm_client.complete_json(
            [{"role": "user", "content": prompt}],
            tier="extraction",
        )
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        logger.error("LLM extraction failed: %s", exc)
        return {"nodes": 0, "edges": 0, "facts": []}

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
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            logger.debug("Second-pass extraction failed, continuing with first pass: %s", exc)

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
        except (KeyError, ValueError, TypeError):
            continue

    edges_count = 0
    extracted_facts: list[dict[str, Any]] = []
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

            edge = await upsert_edge(
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
            extracted_facts.append(
                {
                    "fact_text": edge.fact_text,
                    "predicate": edge.predicate,
                    "category": edge.category or "",
                    "importance": edge.importance,
                    "confidence": edge.confidence,
                    "scope": edge.scope,
                    "emotional_salience": edge.emotional_salience,
                    "emotional_context": edge.emotional_context,
                    "created_at": edge.created_at.isoformat() if edge.created_at else None,
                    "updated_at": edge.updated_at.isoformat() if edge.updated_at else None,
                }
            )
        except (KeyError, ValueError, TypeError):
            continue

    await db.commit()
    return {"nodes": nodes_count, "edges": edges_count, "facts": extracted_facts}
