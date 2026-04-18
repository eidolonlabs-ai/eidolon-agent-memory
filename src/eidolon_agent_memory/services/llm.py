"""LLM client backed by LM Studio (OpenAI-compatible API)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from eidolon_agent_memory.core.config import settings

logger = logging.getLogger(__name__)


def _repair_json(text: str) -> str:
    """
    Apply lightweight repairs to LLM-generated JSON that is almost valid.

    Handles the most common small-model failure modes:
      - Trailing commas before } or ]
      - Text before the opening { or after the closing }
      - Markdown code fences (```json ... ```)
    """
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Extract substring from first { to last } (ignore leading/trailing prose)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    # Remove trailing commas before } or ] (common small-model mistake)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


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
        text = await self.complete(
            full_messages,
            tier=tier,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Strip optional markdown code fences and repair common JSON issues
        text = _repair_json(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse failed after repair (len=%d): %s — snippet: %r",
                len(text),
                exc,
                text[max(0, exc.pos - 40) : exc.pos + 40] if hasattr(exc, "pos") else text[:120],
            )
            raise


llm_client = LLMClient()
