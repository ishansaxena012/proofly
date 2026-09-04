"""The env-configured caps must be enforced, not merely read."""

from __future__ import annotations

import pytest

from app.graph.budget import BudgetedLLMProvider, BudgetExceeded, ResearchBudget
from app.graph.context import JobContext
from app.graph.nodes.planner import planner_node
from app.graph.nodes.research import web_research_node
from app.graph.schemas import ProductResolutionLLM
from app.graph.state import initial_state
from app.models.enums import Channel, SourceStatus
from app.providers.base import LLMProvider
from tests.conftest import run_pipeline
from tests.factories import PRODUCT


def _context(settings, providers, backend, job_id="job-limits") -> JobContext:
    return JobContext.create(
        job_id=job_id,
        product_query="Sony WH-1000XM6",
        demo_mode=True,
        settings=settings,
        providers=providers,
        backend=backend,
        budget=ResearchBudget(settings),
    )


async def test_queries_per_channel_are_capped(settings, providers, backend):
    capped = settings.model_copy(update={"research_max_queries_per_channel": 2})
    ctx = _context(capped, providers, backend)
    state = initial_state(ctx.job_id, "Sony WH-1000XM6", True)
    state["product"] = PRODUCT

    plan = (await planner_node(ctx, state))["plan"]
    assert len(plan.web_queries) == 2
    assert len(plan.reddit_queries) == 2
    assert len(plan.youtube_queries) == 2
    assert ctx.budget.query_allowance(Channel.WEB) == 0
    # Trimming a long candidate list is normal operation, not a degraded run.
    assert ctx.budget.notes
    assert ctx.budget.degradations == []


async def test_max_sources_is_enforced(settings, providers, backend):
    capped = settings.model_copy(update={"research_max_sources": 2})
    ctx = _context(capped, providers, backend)
    state = initial_state(ctx.job_id, "Sony WH-1000XM6", True)
    state["product"] = PRODUCT
    state.update(await planner_node(ctx, state))

    result = await web_research_node(ctx, state)
    fetched = [s for s in result["sources"] if s.status == SourceStatus.FETCHED]
    assert len(fetched) == 2
    assert ctx.budget.source_allowance == 0
    assert any("RESEARCH_MAX_SOURCES" in note for note in ctx.budget.notes)


async def test_document_token_budget_stops_ingestion(settings, providers, backend):
    capped = settings.model_copy(update={"research_max_document_tokens": 400})
    ctx = _context(capped, providers, backend)
    state = initial_state(ctx.job_id, "Sony WH-1000XM6", True)
    state["product"] = PRODUCT
    state.update(await planner_node(ctx, state))

    result = await web_research_node(ctx, state)
    assert ctx.budget.document_tokens <= 400
    assert len(result["sources"]) < len(providers.search._documents) + 1
    assert any("RESEARCH_MAX_DOCUMENT_TOKENS" in note for note in ctx.budget.notes)


def test_pages_per_source_is_enforced(settings):
    budget = ResearchBudget(settings.model_copy(update={"research_max_pages_per_source": 1}))
    assert budget.take_page("https://example.invalid/a") is True
    assert budget.take_page("https://example.invalid/a") is False
    assert budget.take_page("https://example.invalid/b") is True


def test_duration_cap_raises_once_the_deadline_passes(settings):
    ticks = iter([0.0, 0.0, 700.0, 700.0])
    budget = ResearchBudget(
        settings.model_copy(update={"research_max_duration_seconds": 600}),
        clock=lambda: next(ticks),
    )
    budget.check_deadline()
    with pytest.raises(BudgetExceeded) as exc:
        budget.check_deadline()
    assert exc.value.limit_name == "RESEARCH_MAX_DURATION_SECONDS"


class _CountingLLM(LLMProvider):
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt, *, task="", context=None):
        self.calls += 1
        return "text"

    async def generate_structured(self, prompt, schema, *, task="", context=None):
        self.calls += 1
        return schema()

    async def embed(self, texts):
        self.calls += 1
        return [[0.0] for _ in texts]


async def test_llm_call_cap_switches_to_the_deterministic_engine(settings):
    budget = ResearchBudget(settings.model_copy(update={"research_max_llm_calls": 2}))
    inner = _CountingLLM()
    llm = BudgetedLLMProvider(inner, budget)

    for _ in range(5):
        await llm.generate_structured("p", ProductResolutionLLM, task="product_resolution",
                                      context={"query": "Sony WH-1000XM6"})

    assert inner.calls == 2
    assert budget.llm_calls == 2
    assert any("RESEARCH_MAX_LLM_CALLS" in note for note in budget.degradations)


class _BrokenLLM(LLMProvider):
    name = "broken"

    async def generate(self, prompt, *, task="", context=None):
        raise RuntimeError("provider exploded")

    async def generate_structured(self, prompt, schema, *, task="", context=None):
        raise RuntimeError("provider exploded")

    async def embed(self, texts):
        raise RuntimeError("provider exploded")


async def test_a_failing_llm_degrades_instead_of_crashing(settings):
    budget = ResearchBudget(settings)
    llm = BudgetedLLMProvider(_BrokenLLM(), budget)
    result = await llm.generate_structured(
        "p", ProductResolutionLLM, task="product_resolution", context={"query": "Sony WH-1000XM6"}
    )
    assert result.brand == "Sony"
    assert any("LLM call failed" in note for note in budget.degradations)
    assert await llm.embed(["x"])


async def test_a_channel_outage_degrades_the_run_instead_of_failing_it(
    settings, providers, backend, monkeypatch
):
    async def explode(*args, **kwargs):
        raise RuntimeError("reddit is down")

    monkeypatch.setattr(providers.reddit, "search", explode)
    ctx = _context(settings, providers, backend, job_id="job-degraded")

    state = await run_pipeline(ctx)

    assert state["terminal_status"] == "PARTIALLY_COMPLETED"
    assert state["channel_outcomes"]["REDDIT"]["status"] == "FAILED"
    assert state["channel_outcomes"]["WEB"]["status"] == "OK"
    assert state["report"] is not None
    assert any("REDDIT research was unavailable" in c for c in state["report"].caveats)
