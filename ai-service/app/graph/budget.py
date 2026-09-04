"""Hard cost/safety caps.

Every limit in ``.env.example`` is enforced here, not merely read. The graph asks
the budget for permission before each query, each fetch, each LLM call, and each
document it ingests; the wall-clock deadline is checked at every node boundary.
"""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.models.enums import Channel
from app.providers.base import LLMProvider
from app.providers.llm import MockLLMProvider

log = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    """Raised when a hard cap would be breached."""

    def __init__(self, limit_name: str, message: str) -> None:
        super().__init__(message)
        self.limit_name = limit_name


class ResearchBudget:
    def __init__(self, settings: Settings, *, clock=time.monotonic) -> None:
        self._settings = settings
        self._clock = clock
        self.started_at = clock()
        self.queries_per_channel: dict[str, int] = {}
        self.sources_used = 0
        self.pages_per_source: dict[str, int] = {}
        self.document_tokens = 0
        self.llm_calls = 0
        # ``notes`` is every cap that bit; ``degradations`` is the subset that
        # actually reduced the quality of the result. Trimming a long candidate
        # query list to the configured per-channel cap is normal operation, not
        # a degraded run.
        self.notes: list[str] = []
        self.degradations: list[str] = []

    # ── time ───────────────────────────────────────────────────────────────

    @property
    def elapsed_seconds(self) -> float:
        return self._clock() - self.started_at

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self._settings.research_max_duration_seconds - self.elapsed_seconds)

    def deadline_reached(self) -> bool:
        return self.remaining_seconds <= 0

    def check_deadline(self) -> None:
        if self.deadline_reached():
            raise BudgetExceeded(
                "RESEARCH_MAX_DURATION_SECONDS",
                f"job exceeded the {self._settings.research_max_duration_seconds}s duration cap",
            )

    # ── queries ────────────────────────────────────────────────────────────

    def query_allowance(self, channel: Channel) -> int:
        used = self.queries_per_channel.get(channel.value, 0)
        return max(0, self._settings.research_max_queries_per_channel - used)

    def take_queries(self, channel: Channel, queries: list[str]) -> list[str]:
        """Trim a query list down to what the per-channel cap still allows."""

        allowance = self.query_allowance(channel)
        permitted = queries[:allowance]
        self.queries_per_channel[channel.value] = (
            self.queries_per_channel.get(channel.value, 0) + len(permitted)
        )
        if len(permitted) < len(queries):
            self.note(
                f"Only the first {self._settings.research_max_queries_per_channel} planned "
                f"{channel.value.lower()} queries were run "
                f"(RESEARCH_MAX_QUERIES_PER_CHANNEL).",
                degrading=False,
            )
        return permitted

    # ── sources ────────────────────────────────────────────────────────────

    @property
    def source_allowance(self) -> int:
        return max(0, self._settings.research_max_sources - self.sources_used)

    def sources_exhausted(self) -> bool:
        """True once ``RESEARCH_MAX_SOURCES`` is reached, recording the reason."""

        if self.source_allowance > 0:
            return False
        self.note(
            f"Source ingestion stopped at RESEARCH_MAX_SOURCES="
            f"{self._settings.research_max_sources}; further results were not analysed."
        )
        return True

    def take_source(self) -> bool:
        if self.sources_exhausted():
            return False
        self.sources_used += 1
        return True

    def take_page(self, source_key: str) -> bool:
        used = self.pages_per_source.get(source_key, 0)
        if used >= self._settings.research_max_pages_per_source:
            return False
        self.pages_per_source[source_key] = used + 1
        return True

    # ── documents ──────────────────────────────────────────────────────────

    def take_document_tokens(self, tokens: int) -> bool:
        if self.document_tokens + tokens > self._settings.research_max_document_tokens:
            self.note(
                f"Document ingestion stopped at RESEARCH_MAX_DOCUMENT_TOKENS="
                f"{self._settings.research_max_document_tokens}."
            )
            return False
        self.document_tokens += tokens
        return True

    # ── LLM ────────────────────────────────────────────────────────────────

    @property
    def llm_allowance(self) -> int:
        return max(0, self._settings.research_max_llm_calls - self.llm_calls)

    def take_llm_call(self) -> bool:
        if self.llm_allowance <= 0:
            self.note(
                f"LLM budget exhausted at RESEARCH_MAX_LLM_CALLS="
                f"{self._settings.research_max_llm_calls}; remaining analysis used the "
                f"deterministic rule-based engine."
            )
            return False
        self.llm_calls += 1
        return True

    # ── notes ──────────────────────────────────────────────────────────────

    def note(self, message: str, *, degrading: bool = True) -> None:
        if message not in self.notes:
            self.notes.append(message)
            log.info("budget: %s", message)
        if degrading and message not in self.degradations:
            self.degradations.append(message)

    def snapshot(self) -> dict:
        return {
            "elapsedSeconds": round(self.elapsed_seconds, 3),
            "llmCalls": self.llm_calls,
            "sources": self.sources_used,
            "documentTokens": self.document_tokens,
            "queriesPerChannel": dict(self.queries_per_channel),
        }


class BudgetedLLMProvider(LLMProvider):
    """Wraps an ``LLMProvider`` and enforces ``RESEARCH_MAX_LLM_CALLS``.

    Once the cap is hit — or when the underlying provider errors — calls are
    served by the deterministic rule engine instead. The pipeline keeps running
    and the degradation is disclosed in the report caveats.
    """

    name = "budgeted"

    def __init__(self, inner: LLMProvider, budget: ResearchBudget) -> None:
        self._inner = inner
        self._budget = budget
        self._fallback = inner if isinstance(inner, MockLLMProvider) else MockLLMProvider()

    @property
    def inner_name(self) -> str:
        return self._inner.name

    def _permitted(self) -> bool:
        # The deterministic engine costs nothing, so it is never rate limited.
        if isinstance(self._inner, MockLLMProvider):
            return True
        return self._budget.take_llm_call()

    async def generate(self, prompt: str, *, task: str = "", context: dict | None = None) -> str:
        if not self._permitted():
            return await self._fallback.generate(prompt, task=task, context=context)
        try:
            return await self._inner.generate(prompt, task=task, context=context)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
            self._budget.note(f"LLM call failed ({exc}); used the deterministic engine instead.")
            return await self._fallback.generate(prompt, task=task, context=context)

    async def generate_structured(
        self,
        prompt: str,
        schema,
        *,
        task: str = "",
        context: dict | None = None,
    ):
        if not self._permitted():
            return await self._fallback.generate_structured(
                prompt, schema, task=task, context=context
            )
        try:
            return await self._inner.generate_structured(prompt, schema, task=task, context=context)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
            self._budget.note(f"LLM call failed ({exc}); used the deterministic engine instead.")
            return await self._fallback.generate_structured(
                prompt, schema, task=task, context=context
            )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._permitted():
            return await self._fallback.embed(texts)
        try:
            return await self._inner.embed(texts)
        except Exception as exc:  # noqa: BLE001
            self._budget.note(f"Embedding call failed ({exc}); used deterministic embeddings.")
            return await self._fallback.embed(texts)
