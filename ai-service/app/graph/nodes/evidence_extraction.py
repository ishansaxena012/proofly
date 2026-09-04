"""Node 6 — evidence extraction.

Passages in, structured evidence out. Three things happen here that keep the rest
of the pipeline honest:

* every extracted item is checked back against the passage it claims to come
  from, so text no source contained cannot enter the evidence store;
* sources are clustered into independence groups, so syndicated and
  manufacturer-derived copies cannot inflate confidence later;
* evidence that recurs across three or more independent groups is relabelled
  ``REPEATED_PATTERN``, which is what separates a real pattern from an anecdote.
"""

from __future__ import annotations

import logging

from app.graph.context import JobContext
from app.graph.nodes.planner import dimensions_from_plan
from app.graph.prompts import evidence_extraction_prompt
from app.graph.schemas import EvidenceExtractionResult
from app.graph.state import ResearchState
from app.models.domain import Evidence, Passage, Source
from app.models.enums import (
    EventType,
    EvidenceType,
    JobStatus,
    Sentiment,
    SourceStatus,
    Strength,
)
from app.providers.llm import TASK_EVIDENCE_EXTRACTION
from app.services import heuristics as h
from app.services.independence import cluster_sources

log = logging.getLogger(__name__)

PASSAGE_BATCH = 4
REPEATED_PATTERN_MIN_GROUPS = 3


def _enum_or(value: str, enum_cls, default):
    try:
        return enum_cls(str(value).strip().upper())
    except ValueError:
        return default


async def evidence_extraction_node(ctx: JobContext, state: ResearchState) -> dict:
    ctx.budget.check_deadline()
    await ctx.backend.post_status(ctx.job_id, JobStatus.EXTRACTING_EVIDENCE)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.EVIDENCE_EXTRACTION_STARTED,
        "Extracting structured evidence from collected sources.",
        {"sources": len(state.get("sources", [])), "passages": len(state.get("passages", []))},
    )

    sources: list[Source] = list(state.get("sources", []))
    passages: list[Passage] = list(state.get("passages", []))
    plan = state["plan"]
    product = state["product"]
    product_name = product.canonical_name or product.raw_query
    dimensions = dimensions_from_plan(plan)
    dimension_payload = [
        {"name": dimension.name, "rationale": dimension.rationale, "keywords": list(dimension.keywords)}
        for dimension in dimensions
    ]
    known_topics = {dimension.name.lower(): dimension.name for dimension in dimensions}

    cluster = cluster_sources(sources)
    # Push the independence grouping back to the backend so persisted sources
    # carry it too.
    await ctx.backend.post_sources(ctx.job_id, sources)

    source_by_id = {source.id: source for source in sources}
    passage_by_id = {passage.id: passage for passage in passages}
    passages_by_source: dict[str, list[Passage]] = {}
    for passage in passages:
        passages_by_source.setdefault(passage.source_id, []).append(passage)

    evidence: list[Evidence] = []
    limitations: list[str] = []
    rejected = 0

    for source_id, source_passages in passages_by_source.items():
        source = source_by_id.get(source_id)
        if source is None or source.status != SourceStatus.FETCHED:
            continue
        for start in range(0, len(source_passages), PASSAGE_BATCH):
            ctx.budget.check_deadline()
            batch = source_passages[start : start + PASSAGE_BATCH]
            payload = [
                {
                    "id": passage.id,
                    "text": passage.text,
                    "source_type": source.source_type.value,
                    "channel": source.channel.value,
                    "authority": source.authority_score,
                }
                for passage in batch
            ]
            try:
                result = await ctx.llm.generate_structured(
                    evidence_extraction_prompt(product_name, payload, dimension_payload),
                    EvidenceExtractionResult,
                    task=TASK_EVIDENCE_EXTRACTION,
                    context={"passages": payload, "dimensions": dimension_payload},
                )
            except Exception as exc:  # noqa: BLE001 - a bad batch must not kill the job
                log.warning("evidence extraction failed for source %s: %s", source_id, exc)
                limitations.append(
                    "Some passages could not be analysed and were excluded from the evidence base."
                )
                continue

            for item in result.items:
                passage = passage_by_id.get(item.passage_id)
                if passage is None or passage.source_id != source_id:
                    rejected += 1
                    continue
                text = (item.text or "").strip()
                if not text or not h.grounded_in(text, passage.text):
                    # The model produced text the passage does not contain.
                    rejected += 1
                    continue
                topic = known_topics.get((item.topic or "").strip().lower())
                if topic is None:
                    routed, score = h.topic_for(text, dimensions)
                    if not routed or score < 1:
                        rejected += 1
                        continue
                    topic = routed
                evidence.append(
                    Evidence(
                        research_job_id=ctx.job_id,
                        source_id=source_id,
                        passage_id=passage.id,
                        topic=topic,
                        sentiment=_enum_or(item.sentiment, Sentiment, Sentiment.NEUTRAL),
                        evidence_type=_enum_or(item.evidence_type, EvidenceType, EvidenceType.CLAIM),
                        strength=_enum_or(item.strength, Strength, Strength.MODERATE),
                        text=text,
                    )
                )

    evidence = _deduplicate_within_groups(evidence, source_by_id)
    _label_repeated_patterns(evidence, source_by_id)

    if rejected:
        log.info("job %s rejected %d ungrounded evidence candidate(s)", ctx.job_id, rejected)
    if not evidence:
        limitations.append(
            "No usable evidence could be extracted from the collected sources."
        )
    if cluster.clustered_source_ids:
        limitations.append(
            f"{sum(len(group) for group in cluster.clustered_source_ids)} source(s) were found to "
            f"be near-duplicates or manufacturer-derived and were grouped into "
            f"{len(cluster.clustered_source_ids)} shared independence group(s); they count once "
            f"towards confidence."
        )

    await ctx.backend.post_evidence(ctx.job_id, evidence)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.EVIDENCE_EXTRACTION_COMPLETED,
        f"Extracted {len(evidence)} pieces of evidence from {len(passages_by_source)} source(s).",
        {
            "evidenceCount": len(evidence),
            "rejectedUngrounded": rejected,
            "independenceGroups": cluster.group_count,
            "topics": sorted({item.topic for item in evidence}),
        },
    )

    # ``sources`` uses a merge-by-id reducer, so returning the mutated list
    # updates the stored sources with their independence group ids rather than
    # duplicating them.
    return {"evidence": evidence, "sources": sources, "limitations": limitations}


def _deduplicate_within_groups(
    evidence: list[Evidence], source_by_id: dict[str, Source]
) -> list[Evidence]:
    """Identical text repeated inside one independence group is one observation."""

    seen: set[tuple[str, str]] = set()
    kept: list[Evidence] = []
    for item in evidence:
        source = source_by_id.get(item.source_id)
        group = (source.independence_group_id if source else None) or item.source_id
        key = (group, h.normalise(item.text))
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _label_repeated_patterns(evidence: list[Evidence], source_by_id: dict[str, Source]) -> None:
    """Promote anecdotes to REPEATED_PATTERN when independent groups agree."""

    buckets: dict[tuple[str, str], set[str]] = {}
    for item in evidence:
        source = source_by_id.get(item.source_id)
        group = (source.independence_group_id if source else None) or item.source_id
        buckets.setdefault((item.topic, item.sentiment.value), set()).add(group)

    for item in evidence:
        groups = buckets.get((item.topic, item.sentiment.value), set())
        if len(groups) >= REPEATED_PATTERN_MIN_GROUPS and item.evidence_type in (
            EvidenceType.ANECDOTE,
            EvidenceType.CUSTOMER_EXPERIENCE,
        ):
            item.evidence_type = EvidenceType.REPEATED_PATTERN
            if item.strength == Strength.WEAK:
                item.strength = Strength.MODERATE
