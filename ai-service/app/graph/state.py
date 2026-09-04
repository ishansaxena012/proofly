"""LangGraph state definition.

The three research channels run as parallel branches, so any field they all write
needs a reducer. Everything in the state is serialisable, which is what makes the
Redis checkpointer able to resume a crashed run.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from app.models.domain import (
    Claim,
    Conflict,
    Document,
    Evidence,
    Passage,
    ProductResolution,
    Report,
    ReportSection,
    Source,
)


def append_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return list(left or []) + list(right or [])


def append_unique_strings(left: list[str] | None, right: list[str] | None) -> list[str]:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def merge_by_id(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Append new items, replace existing ones with the same ``id``.

    Lets a later node hand back an updated copy of a record (for example a source
    that has just been assigned an independence group) without duplicating it.
    """

    merged = list(left or [])
    index = {getattr(item, "id", None): position for position, item in enumerate(merged)}
    for item in right or []:
        key = getattr(item, "id", None)
        if key is not None and key in index:
            merged[index[key]] = item
        else:
            index[key] = len(merged)
            merged.append(item)
    return merged


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class ChannelOutcome(TypedDict, total=False):
    status: str  # OK | FAILED | SKIPPED
    sources: int
    error: str


class ResearchState(TypedDict, total=False):
    # inputs
    job_id: str
    product_query: str
    demo_mode: bool

    # stage outputs
    product: ProductResolution | None
    plan: Any  # ResearchPlan
    sources: Annotated[list[Source], merge_by_id]
    documents: Annotated[list[Document], append_list]
    passages: Annotated[list[Passage], append_list]
    channel_outcomes: Annotated[dict[str, ChannelOutcome], merge_dicts]
    limitations: Annotated[list[str], append_unique_strings]

    evidence: list[Evidence]
    claims: list[Claim]
    conflicts: list[Conflict]
    report: Report | None
    sections: list[ReportSection]

    # terminal bookkeeping
    terminal_status: str
    error_code: str | None
    error_message: str | None
    clarification_needed: bool


def initial_state(job_id: str, product_query: str, demo_mode: bool) -> ResearchState:
    return ResearchState(
        job_id=job_id,
        product_query=product_query,
        demo_mode=demo_mode,
        product=None,
        plan=None,
        sources=[],
        documents=[],
        passages=[],
        channel_outcomes={},
        limitations=[],
        evidence=[],
        claims=[],
        conflicts=[],
        report=None,
        sections=[],
        terminal_status="",
        error_code=None,
        error_message=None,
        clarification_needed=False,
    )
