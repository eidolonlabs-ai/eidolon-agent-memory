"""LLM client backed by LM Studio (OpenAI-compatible API)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai import OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from eidolon_agent_memory.core.config import settings

logger = logging.getLogger(__name__)


def _extract_balanced_json_object(text: str) -> str:
    """Return the first balanced JSON object substring, or original text if none found."""
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return text


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _repair_json(text: str) -> str:
    """
    Apply lightweight repairs to LLM-generated JSON that is almost valid.

    Handles the most common small-model failure modes:
      - Trailing commas before } or ]
      - Text before the opening { or after the closing }
      - Markdown code fences (```json ... ```)
    """
    # Strip markdown code fences first.
    text = _strip_code_fences(text)

    # Extract first balanced JSON object and ignore leading/trailing prose.
    text = _extract_balanced_json_object(text)

    # Remove trailing commas before } or ] (common small-model mistake)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Remove non-printing control chars that occasionally break JSON parsing.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    return text


def _message_text(msg: Any) -> str:
    content = msg.content or ""
    if content:
        return content
    raw = msg.model_dump() if hasattr(msg, "model_dump") else {}
    return raw.get("reasoning_content") or ""


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base,
            timeout=120.0,  # 2-minute timeout per request to avoid infinite hangs
        )

    def _resolve_model(self, tier: str | None) -> str:
        match tier:
            case "extraction":
                return settings.llm_extraction_model
            case "utility":
                return settings.llm_utility_model
            case _:
                return settings.llm_cognitive_model

    async def complete(
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        tier: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        resp = await self._client.chat.completions.create(
            model=model or self._resolve_model(tier),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        msg = resp.choices[0].message
        # Some LM Studio thinking models put output in reasoning_content (e.g. QwQ, Gemma-4)
        # and leave content empty. Fall back to reasoning_content if content is empty.
        content = msg.content or ""
        if not content:
            # Check for thinking model field (LM Studio extension)
            raw = msg.model_dump() if hasattr(msg, "model_dump") else {}
            content = raw.get("reasoning_content") or ""
        return content

    async def complete_json(
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        tier: str | None = "extraction",
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Any:
        """
        Complete and parse the response as JSON.
        Appends a system instruction to always respond with valid JSON.
        """
        system_msg: ChatCompletionMessageParam = {
            "role": "system",
            "content": "Always respond with valid JSON only. No markdown fences, no prose.",
        }
        full_messages = [system_msg, *messages]
        used_model = model or self._resolve_model(tier)

        async def _raw_json_call(extra_messages: list[ChatCompletionMessageParam] | None = None) -> str:
            call_messages = [*full_messages, *(extra_messages or [])]
            try:
                resp = await self._client.chat.completions.create(
                    model=used_model,
                    messages=call_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                return _message_text(resp.choices[0].message)
            except (OpenAIError, httpx.HTTPError, TypeError, ValueError, RuntimeError):
                return await self.complete(
                    call_messages,
                    tier=tier,
                    model=used_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

        def _parse_candidates(raw_text: str) -> Any:
            candidates = [
                raw_text.strip(),
                _strip_code_fences(raw_text),
                _extract_balanced_json_object(raw_text),
                _repair_json(raw_text),
            ]
            seen: set[str] = set()
            last_error: json.JSONDecodeError | None = None
            for candidate in candidates:
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue
            if last_error is not None:
                raise last_error
            raise json.JSONDecodeError("No JSON candidates to parse", raw_text, 0)

        first_text = await _raw_json_call()
        try:
            return _parse_candidates(first_text)
        except json.JSONDecodeError as exc_first:
            logger.warning(
                "Initial JSON parse failed (len=%d): %s — attempting corrective retry",
                len(first_text),
                exc_first,
            )

        corrective_msg: ChatCompletionMessageParam = {
            "role": "system",
            "content": (
                "Your previous response was invalid JSON. Return the same answer as valid compact JSON only. "
                "Do not include markdown fences, comments, or trailing commas."
            ),
        }
        second_text = await _raw_json_call(extra_messages=[corrective_msg])
        try:
            return _parse_candidates(second_text)
        except json.JSONDecodeError as exc:
            repaired = _repair_json(second_text)
            logger.error(
                "JSON parse failed after retry+repair (len=%d): %s — snippet: %r",
                len(repaired),
                exc,
                repaired[max(0, exc.pos - 40) : exc.pos + 40] if hasattr(exc, "pos") else repaired[:120],
            )
            raise


llm_client = LLMClient()
