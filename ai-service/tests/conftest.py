"""Shared test fixtures.

Everything here is offline: providers are the deterministic fixture mocks and the
backend callback client is wired to an ``httpx.MockTransport``. No test makes a
network call.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.graph.budget import ResearchBudget
from app.graph.context import JobContext
from app.graph.pipeline import build_graph
from app.graph.state import initial_state
from app.providers.factory import build_providers
from app.services.backend_client import BackendClient

DEMO_JOB_ID = "11111111-1111-4111-8111-111111111111"
GOLDEN_QUERY = "Sony WH-1000XM6"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        demo_mode=True,
        internal_api_key="test-internal-key",
        backend_internal_url="http://backend.test",
        redis_url="",
        gemini_api_key="",
        youtube_api_key="",
        search_provider="mock",
        research_max_queries_per_channel=5,
        research_max_sources=25,
        research_max_pages_per_source=1,
        research_max_document_tokens=200_000,
        research_max_llm_calls=60,
        research_max_duration_seconds=600,
    )


@pytest.fixture
def backend_calls() -> list[dict]:
    return []


@pytest.fixture
def backend(settings: Settings, backend_calls: list[dict]) -> BackendClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content or b"{}"
        backend_calls.append(
            {
                "path": request.url.path,
                "key": request.headers.get("X-Internal-Key"),
                "json": json.loads(body),
            }
        )
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        base_url=settings.backend_internal_url,
        transport=httpx.MockTransport(handler),
        headers={"X-Internal-Key": settings.internal_api_key},
    )
    return BackendClient(settings, client=client)


@pytest.fixture
def providers(settings: Settings):
    return build_providers(settings, demo_mode=True)


@pytest.fixture
def job_context(settings, providers, backend) -> JobContext:
    return JobContext.create(
        job_id=DEMO_JOB_ID,
        product_query=GOLDEN_QUERY,
        demo_mode=True,
        settings=settings,
        providers=providers,
        backend=backend,
        budget=ResearchBudget(settings),
    )


async def run_pipeline(ctx: JobContext, query: str | None = None) -> dict:
    """Run the whole graph end to end with in-memory checkpointing."""

    graph = build_graph(ctx)
    return await graph.ainvoke(
        initial_state(ctx.job_id, query or ctx.product_query, ctx.demo_mode),
        config={"configurable": {"thread_id": ctx.job_id}, "recursion_limit": 60},
    )


@pytest.fixture
async def golden_run(job_context: JobContext) -> dict:
    return await run_pipeline(job_context)
