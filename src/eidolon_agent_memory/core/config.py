from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://eidolon_agent_memory:eidolon_agent_memory@localhost:25433/eidolon_agent_memory"
    )

    # ── LLM (OpenAI-compatible — points to LM Studio by default) ─────────────
    llm_api_base: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_cognitive_model: str = "lmstudio-community/gemma-3-12b-it-GGUF"
    llm_extraction_model: str = "lmstudio-community/gemma-3-12b-it-GGUF"
    llm_utility_model: str = "lmstudio-community/gemma-3-12b-it-GGUF"

    # ── Embeddings (OpenAI-compatible — LM Studio) ────────────────────────────
    embedding_api_base: str = "http://127.0.0.1:1234/v1"
    embedding_api_key: str = "lm-studio"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    embedding_dimensions: int = 768  # nomic-embed default; 1536 for OpenAI ada-002

    # ── MCP server ────────────────────────────────────────────────────────────
    mcp_transport: str = "http"  # "http" or "stdio"
    mcp_port: int = 3100
    mcp_host: str = "0.0.0.0"

    # ── Auth ──────────────────────────────────────────────────────────────────
    api_key_secret: str = "change-me-in-production"

    # ── Background worker ─────────────────────────────────────────────────────
    session_idle_minutes: int = 15   # auto-end sessions idle this long
    message_retention_days: int = 7  # delete session_messages N days post-processing


settings = Settings()
