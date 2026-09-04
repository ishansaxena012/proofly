"""Research planning: universal baseline + category-specific dimensions, with a
generic fallback for categories the catalog does not know."""

from __future__ import annotations

from app.graph.catalog import UNIVERSAL_DIMENSIONS, resolve_category_key
from app.graph.nodes.planner import dimensions_from_plan, plan_dimensions, planner_node
from app.graph.state import initial_state
from app.models.domain import ProductResolution
from app.models.enums import Channel, EventType, JobStatus

UNIVERSAL_NAMES = {dimension.name for dimension in UNIVERSAL_DIMENSIONS}


def _names(product: str, category: str | None) -> set[str]:
    _, _, dimensions = plan_dimensions(product, category, product)
    return {dimension.name for dimension in dimensions}


def test_headphone_plan_has_category_specific_dimensions():
    names = _names("Sony WH-1000XM6", "headphones")
    assert {"Sound Quality", "Noise Cancellation", "Microphone & Call Quality"} <= names
    assert names >= UNIVERSAL_NAMES


def test_laptop_plan_differs_from_headphones():
    names = _names("Dell XPS 13 9340", "laptop")
    assert {"Thermals & Noise", "Keyboard & Trackpad", "Display"} <= names
    assert "Noise Cancellation" not in names
    assert names >= UNIVERSAL_NAMES


def test_smartphone_plan_differs_again():
    names = _names("Google Pixel 9 Pro", "smartphone")
    assert {"Camera Quality", "Software & Updates", "Durability"} <= names
    assert "Sound Quality" not in names


def test_kitchen_appliance_plan():
    names = _names("Sage Barista Express", "espresso machine")
    assert {"Output Quality", "Cleaning & Maintenance"} <= names


def test_unknown_category_falls_back_to_generic_not_headphones():
    key, matched = resolve_category_key("garden hose reel")
    assert key == "generic"
    assert matched is False
    names = _names("Hozelock Auto Reel 2401", "garden hose reel")
    assert {"Core Performance", "Everyday Practicality"} <= names
    assert "Noise Cancellation" not in names
    assert names >= UNIVERSAL_NAMES


async def test_planner_node_builds_capped_queries(job_context, backend_calls, settings):
    state = initial_state(job_context.job_id, "Sony WH-1000XM6", True)
    state["product"] = ProductResolution(
        raw_query="Sony WH-1000XM6",
        canonical_name="Sony WH-1000XM6",
        brand="Sony",
        model="WH-1000XM6",
        category="headphones",
        resolution_confidence=0.95,
    )

    result = await planner_node(job_context, state)
    plan = result["plan"]

    assert plan.category == "headphones"
    assert plan.category_matched is True
    assert len(plan.dimensions) >= 10

    cap = settings.research_max_queries_per_channel
    for queries in (plan.web_queries, plan.reddit_queries, plan.youtube_queries):
        assert 0 < len(queries) <= cap
        assert all("Sony WH-1000XM6" in query for query in queries)

    assert job_context.budget.query_allowance(Channel.WEB) == 0

    events = [c["json"] for c in backend_calls if c["path"].endswith("/events")]
    assert events[-1]["eventType"] == EventType.RESEARCH_STARTED.value
    statuses = [c["json"]["status"] for c in backend_calls if c["path"].endswith("/status")]
    assert JobStatus.PLANNING_RESEARCH.value in statuses
    assert JobStatus.RESEARCHING.value in statuses


async def test_dimensions_can_be_rebuilt_from_a_stored_plan(job_context):
    state = initial_state(job_context.job_id, "Sony WH-1000XM6", True)
    state["product"] = ProductResolution(
        raw_query="Sony WH-1000XM6",
        canonical_name="Sony WH-1000XM6",
        category="headphones",
        resolution_confidence=0.95,
    )
    plan = (await planner_node(job_context, state))["plan"]

    rebuilt = dimensions_from_plan(plan)
    assert {d.name for d in rebuilt} == {d.name for d in plan.dimensions}
    assert all(dimension.keywords for dimension in rebuilt)
