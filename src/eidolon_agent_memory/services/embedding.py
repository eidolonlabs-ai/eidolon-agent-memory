"""Embedding service backed by LM Studio (OpenAI-compatible API)."""
from __future__ import annotations

from openai import AsyncOpenAI

from eidolon_agent_memory.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_api_base,
            timeout=120.0,  # 2-minute timeout to prevent infinite hangs
        )
        self._model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        """Return a single embedding vector for *text*."""
        resp = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return resp.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of texts (one API call)."""
        resp = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Results are ordered by index
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]


embedding_service = EmbeddingService()
