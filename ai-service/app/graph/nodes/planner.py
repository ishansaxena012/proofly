"""Node 2 — research planning.

The plan is a universal baseline (build quality, reliability, value, ease of use)
plus a category-specific set drawn from the catalog, adapted to the category the
resolver produced. Unknown categories get the generic set, and the plan records
that so the report can disclose it.
"""

from __future__ import annotations

import logging

from app.graph.catalog import Dimension, dimensions_for, resolve_category_key
from app.graph.context import JobContext
from app.graph.prompts import plan_extension_prompt
from app.graph.schemas import PlanExtension
from app.graph.state import ResearchState
from app.models.domain import ResearchDimension, ResearchPlan
from app.models.enums import Channel, EventType, JobStatus
from app.providers.llm import TASK_PLAN_EXTENSION
from app.services.heuristics import words

log = logging.getLogger(__name__)

MAX_EXTRA_DIMENSIONS = 3


def plan_dimensions(product_name: str, category_hint: str | None, raw_query: str) -> tuple[str, bool, list[Dimension]]:
    category_key, matched = resolve_category_key(category_hint, product_name, raw_query)
    return category_key, matched, list(dimensions_for(category_key))


def build_queries(product_name: str, dimensions: list[Dimension], channel: Channel) -> list[str]:
    """Deterministic query construction: the product name always anchors the query."""

    queries: list[str] = []
    if channel is Channel.WEB:
        queries.append(f"{product_name} review")
        queries.append(f"{product_name} problems complaints")
    elif channel is Channel.REDDIT:
        queries.append(f"{product_name} review")
        queries.append(f"{product_name} problems after months")
    else:
        queries.append(f"{product_name} review")

    for dimension in dimensions:
        for term in dimension.query_terms:
            candidate = f"{product_name} {term}"
            if candidate not in queries:
                queries.append(candidate)
    return queries


async def planner_node(ctx: JobContext, state: ResearchState) -> dict:
    ctx.budget.check_deadline()
    product = state["product"]
    assert product is not None  # routing guarantees this
    product_name = product.canonical_name or product.raw_query

    await ctx.backend.post_status(ctx.job_id, JobStatus.PLANNING_RESEARCH)

    category_key, matched, dimensions = plan_dimensions(
        product_name, product.category, product.raw_query
    )

    extension = await ctx.llm.generate_structured(
        plan_extension_prompt(product_name, category_key, [d.name for d in dimensions]),
        PlanExtension,
        task=TASK_PLAN_EXTENSION,
        context={
            "product": product_name,
            "category": category_key,
            "existing": [d.name for d in dimensions],
        },
    )
    existing_names = {d.name.lower() for d in dimensions}
    for extra in extension.dimensions[:MAX_EXTRA_DIMENSIONS]:
        name = (extra.name or "").strip()
        if not name or name.lower() in existing_names:
            continue
        keywords = tuple(token for token in words(name) if len(token) > 2)
        if not keywords:
            continue
        existing_names.add(name.lower())
        dimensions.append(
            Dimension(
                name=name,
                rationale=(extra.rationale or "Proposed for this specific product.").strip(),
                keywords=keywords,
                query_terms=(name.lower(),),
            )
        )

    web_queries = ctx.budget.take_queries(
        Channel.WEB, build_queries(product_name, dimensions, Channel.WEB)
    )
    reddit_queries = ctx.budget.take_queries(
        Channel.REDDIT, build_queries(product_name, dimensions, Channel.REDDIT)
    )
    youtube_queries = ctx.budget.take_queries(
        Channel.YOUTUBE, build_queries(product_name, dimensions, Channel.YOUTUBE)
    )

    plan = ResearchPlan(
        category=category_key,
        category_matched=matched,
        dimensions=[
            ResearchDimension(
                name=dimension.name,
                rationale=dimension.rationale,
                universal=dimension.universal,
                queries=[f"{product_name} {term}" for term in dimension.query_terms],
            )
            for dimension in dimensions
        ],
        web_queries=web_queries,
        reddit_queries=reddit_queries,
        youtube_queries=youtube_queries,
    )

    limitations: list[str] = []
    if not matched:
        limitations.append(
            "The product category was not recognised, so a generic research plan was used "
            "instead of a category-specific one."
        )

    await ctx.backend.post_status(ctx.job_id, JobStatus.RESEARCHING)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.RESEARCH_STARTED,
        f"Planned {len(plan.dimensions)} research dimensions for {product_name}.",
        {
            "category": category_key,
            "categoryMatched": matched,
            "dimensions": [d.name for d in plan.dimensions],
            "webQueries": web_queries,
            "redditQueries": reddit_queries,
            "youtubeQueries": youtube_queries,
        },
    )

    return {"plan": plan, "limitations": limitations}


def dimensions_from_plan(plan: ResearchPlan) -> list[Dimension]:
    """Rebuild catalog dimensions (with keyword vocabulary) from a stored plan."""

    catalog = {d.name: d for d in dimensions_for(plan.category)}
    rebuilt: list[Dimension] = []
    for entry in plan.dimensions:
        known = catalog.get(entry.name)
        if known is not None:
            rebuilt.append(known)
            continue
        keywords = tuple(token for token in words(entry.name) if len(token) > 2)
        rebuilt.append(
            Dimension(
                name=entry.name,
                rationale=entry.rationale,
                keywords=keywords,
                universal=entry.universal,
            )
        )
    return rebuilt
