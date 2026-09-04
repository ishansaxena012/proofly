"""Application configuration.

Every value here maps onto a variable already present in the repository root
``.env.example``. Nothing is hard-coded as a magic number: the cost/safety caps in
particular are read from the environment and enforced for real (see
``app.graph.budget``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── LLM (Gemini, behind LLMProvider) ────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # ── Redis (checkpoints / provider result cache) ─────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Search provider ─────────────────────────────────────────────────────
    # ``auto`` (our default when the var is unset) means: pick the keyless public
    # HTML search implementation unless DEMO_MODE is on.
    search_provider: str = "auto"
    search_api_key: str = ""

    # ── Reddit provider ─────────────────────────────────────────────────────
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "proofly-research-agent/1.0"

    # ── YouTube provider ────────────────────────────────────────────────────
    youtube_api_key: str = ""

    # ── Demo / mock mode ────────────────────────────────────────────────────
    demo_mode: bool = True

    # ── Cost / safety limits (hard caps, enforced in the graph) ─────────────
    research_max_queries_per_channel: int = 5
    research_max_sources: int = 25
    research_max_pages_per_source: int = 1
    research_max_document_tokens: int = 200_000
    research_max_llm_calls: int = 60
    research_max_duration_seconds: int = 600
    research_max_concurrent_jobs: int = 3

    # ── Internal service-to-service auth ────────────────────────────────────
    internal_api_key: str = "dev-internal-key-change-me"

    # ── Service wiring ──────────────────────────────────────────────────────
    ai_service_port: int = 8000
    backend_internal_url: str = "http://localhost:8080"

    # ── Networking knobs for the live providers ─────────────────────────────
    http_timeout_seconds: float = Field(default=20.0)
    http_user_agent: str = "proofly-research-agent/1.0 (+https://github.com/proofly)"

    @property
    def gemini_available(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def youtube_available(self) -> bool:
        return bool(self.youtube_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Used by tests after mutating the environment."""
    get_settings.cache_clear()
