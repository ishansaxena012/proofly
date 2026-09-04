"""Product resolution, including the ambiguity rejection that stops the agent
from silently researching a product the user did not ask for."""

from __future__ import annotations

import pytest

from app.graph.nodes.product_resolver import (
    detect_ambiguity,
    product_resolver_node,
    route_after_resolution,
)
from app.graph.state import initial_state
from app.models.enums import ErrorCode, EventType, JobStatus

AMBIGUOUS = [
    "best Sony headphones",
    "top noise cancelling headphones 2025",
    "which laptop should I buy",
    "Sony WH-1000XM6 vs Bose QuietComfort Ultra",
    "good headphones under $300",
    "headphones",
    "Sony headphones",
    "recommend me a coffee machine",
    "",
]

SPECIFIC = [
    "Sony WH-1000XM6",
    "sony wh-1000xm6",
    "Dell XPS 13 9340",
    "Google Pixel 9 Pro",
    "AirPods Max",
]


@pytest.mark.parametrize("query", AMBIGUOUS)
def test_ambiguous_queries_are_rejected(query):
    ambiguous, reason, guidance = detect_ambiguity(query)
    assert ambiguous, f"{query!r} should be flagged ambiguous"
    assert reason
    assert guidance


@pytest.mark.parametrize("query", SPECIFIC)
def test_specific_queries_resolve(query):
    ambiguous, _, _ = detect_ambiguity(query)
    assert not ambiguous, f"{query!r} should resolve to one product"


def test_clarification_guidance_never_invents_product_names():
    _, _, guidance = detect_ambiguity("best Sony headphones")
    joined = " ".join(guidance).lower()
    # Guidance must be instructions, not made-up model numbers.
    assert "wh-" not in joined
    assert "xm" not in joined


async def test_resolver_short_circuits_on_an_ambiguous_query(job_context, backend_calls):
    state = initial_state(job_context.job_id, "best Sony headphones", True)
    result = await product_resolver_node(job_context, state)

    assert result["clarification_needed"] is True
    assert result["terminal_status"] == JobStatus.FAILED.value
    assert result["error_code"] == ErrorCode.INVALID_PRODUCT.value
    assert result["product"].canonical_name is None
    assert route_after_resolution({**state, **result}) == "clarification"

    events = [c["json"] for c in backend_calls if c["path"].endswith("/events")]
    assert events[-1]["eventType"] == EventType.JOB_FAILED.value
    assert events[-1]["payload"]["errorCode"] == ErrorCode.INVALID_PRODUCT.value

    statuses = [c["json"] for c in backend_calls if c["path"].endswith("/status")]
    assert statuses[-1]["status"] == JobStatus.FAILED.value
    # No product was pushed to the backend, because none was resolved.
    assert not [c for c in backend_calls if c["path"].endswith("/product")]


async def test_resolver_resolves_the_golden_product(job_context, backend_calls):
    state = initial_state(job_context.job_id, "Sony WH-1000XM6", True)
    result = await product_resolver_node(job_context, state)

    product = result["product"]
    assert result["clarification_needed"] is False
    assert product.canonical_name == "Sony WH-1000XM6"
    assert product.brand == "Sony"
    assert product.model == "WH-1000XM6"
    assert product.category == "headphones"
    assert product.resolution_confidence > 0.5
    assert route_after_resolution({**state, **result}) == "planner"

    products = [c["json"] for c in backend_calls if c["path"].endswith("/product")]
    assert products[0]["canonicalName"] == "Sony WH-1000XM6"
