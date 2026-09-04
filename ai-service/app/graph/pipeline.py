"""The research StateGraph.

```
                       ┌── web_research ────┐
START → product_resolver → planner → reddit_research  ├→ evidence_extraction →
                       └── youtube_research ┘
        claim_generation → verification → report_synthesis → END
```

``product_resolver`` can route straight to ``END`` when the query is ambiguous:
Proofly asks for clarification rather than guessing which product to research.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from app.graph.context import JobContext
from app.graph.nodes.claim_generation import claim_generation_node
from app.graph.nodes.evidence_extraction import evidence_extraction_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.product_resolver import product_resolver_node, route_after_resolution
from app.graph.nodes.report_synthesis import report_synthesis_node
from app.graph.nodes.research import (
    reddit_research_node,
    web_research_node,
    youtube_research_node,
)
from app.graph.nodes.verification import verification_node
from app.graph.state import ResearchState

NodeFn = Callable[[JobContext, ResearchState], Awaitable[dict]]


def _bind(ctx: JobContext, node: NodeFn):
    async def run(state: ResearchState) -> dict:
        return await node(ctx, state)

    run.__name__ = node.__name__
    return run


def build_graph(ctx: JobContext, checkpointer=None):
    builder = StateGraph(ResearchState)

    builder.add_node("product_resolver", _bind(ctx, product_resolver_node))
    builder.add_node("planner", _bind(ctx, planner_node))
    builder.add_node("web_research", _bind(ctx, web_research_node))
    builder.add_node("reddit_research", _bind(ctx, reddit_research_node))
    builder.add_node("youtube_research", _bind(ctx, youtube_research_node))
    builder.add_node("evidence_extraction", _bind(ctx, evidence_extraction_node))
    builder.add_node("claim_generation", _bind(ctx, claim_generation_node))
    builder.add_node("verification", _bind(ctx, verification_node))
    builder.add_node("report_synthesis", _bind(ctx, report_synthesis_node))

    builder.add_edge(START, "product_resolver")
    builder.add_conditional_edges(
        "product_resolver",
        route_after_resolution,
        {"planner": "planner", "clarification": END},
    )

    for channel_node in ("web_research", "reddit_research", "youtube_research"):
        builder.add_edge("planner", channel_node)
        builder.add_edge(channel_node, "evidence_extraction")

    builder.add_edge("evidence_extraction", "claim_generation")
    builder.add_edge("claim_generation", "verification")
    builder.add_edge("verification", "report_synthesis")
    builder.add_edge("report_synthesis", END)

    return builder.compile(checkpointer=checkpointer)
