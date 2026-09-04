"""Node 7 — claim generation and conflict detection.

One topic at a time, the evidence for that topic is turned into claims with
explicit ``SUPPORTS`` / ``CONTRADICTS`` / ``CONTEXTUALIZES`` relationships.

Where independent sources disagree, the disagreement is recorded as a first-class
:class:`Conflict` — both positions, both evidence sets, and an explanation of the
condition that separates them. Nothing is resolved by majority vote.
"""

from __future__ import annotations

import logging
import re

from app.graph.context import JobContext
from app.graph.prompts import claim_generation_prompt, conflict_explanation_prompt
from app.graph.schemas import ClaimGenerationResult, ConflictExplanation
from app.graph.state import ResearchState
from app.models.domain import (
    Claim,
    ClaimEvidenceLink,
    Conflict,
    ConflictPosition,
    Evidence,
    Source,
)
from app.models.enums import (
    ClaimStatus,
    EventType,
    JobStatus,
    Relationship,
    Sentiment,
    Strength,
)
from app.providers.llm import (
    TASK_CLAIM_GENERATION,
    TASK_CONFLICT_EXPLANATION,
    MockLLMProvider,
)
from app.services.conflict import is_genuine_conflict
from app.services.heuristics import dominant_qualifiers

log = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER_RE.finditer(text)}


def _evidence_payload(items: list[Evidence], source_by_id: dict[str, Source]) -> list[dict]:
    payload = []
    for item in items:
        source = source_by_id.get(item.source_id)
        payload.append(
            {
                "id": item.id,
                "text": item.text,
                "topic": item.topic,
                "sentiment": item.sentiment.value,
                "strength": item.strength.value,
                "evidence_type": item.evidence_type.value,
                "source_id": item.source_id,
                "source_type": source.source_type.value if source else "GENERIC",
                "independence_group_id": source.independence_group_id if source else None,
            }
        )
    return payload


def _groups_for(items: list[Evidence], source_by_id: dict[str, Source]) -> set[str]:
    groups: set[str] = set()
    for item in items:
        source = source_by_id.get(item.source_id)
        groups.add((source.independence_group_id if source else None) or item.source_id)
    return groups


def _has_strong(items: list[Evidence]) -> bool:
    return any(item.strength == Strength.STRONG for item in items)


def _initial_status(
    supporting: list[Evidence], contradicting: list[Evidence], source_by_id: dict[str, Source]
) -> ClaimStatus:
    if not supporting:
        return ClaimStatus.INSUFFICIENT_EVIDENCE
    supporting_groups = _groups_for(supporting, source_by_id)
    if contradicting:
        contradicting_groups = _groups_for(contradicting, source_by_id)
        if is_genuine_conflict(
            supporting_groups,
            contradicting_groups,
            positive_has_strong=_has_strong(supporting),
            negative_has_strong=_has_strong(contradicting),
        ):
            return ClaimStatus.CONTESTED
        # A dissenting minority that is not substantial enough to be a conflict
        # still stops the claim from being fully supported.
        return ClaimStatus.PARTIALLY_SUPPORTED
    if len(supporting_groups) >= 2:
        return ClaimStatus.SUPPORTED
    return ClaimStatus.PARTIALLY_SUPPORTED


async def claim_generation_node(ctx: JobContext, state: ResearchState) -> dict:
    ctx.budget.check_deadline()
    await ctx.backend.post_status(ctx.job_id, JobStatus.ANALYZING)

    evidence: list[Evidence] = list(state.get("evidence", []))
    sources: list[Source] = list(state.get("sources", []))
    source_by_id = {source.id: source for source in sources}
    evidence_by_id = {item.id: item for item in evidence}
    product = state["product"]
    product_name = product.canonical_name or product.raw_query

    by_topic: dict[str, list[Evidence]] = {}
    for item in evidence:
        by_topic.setdefault(item.topic, []).append(item)

    fallback_llm = MockLLMProvider()
    claims: list[Claim] = []
    conflicts: list[Conflict] = []
    limitations: list[str] = []

    for topic in sorted(by_topic):
        ctx.budget.check_deadline()
        topic_evidence = by_topic[topic]
        payload = _evidence_payload(topic_evidence, source_by_id)
        valid_ids = {item["id"] for item in payload}

        try:
            result = await ctx.llm.generate_structured(
                claim_generation_prompt(product_name, topic, payload),
                ClaimGenerationResult,
                task=TASK_CLAIM_GENERATION,
                context={"topic": topic, "evidence": payload, "product": product_name},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("claim generation failed for topic %s: %s", topic, exc)
            result = await fallback_llm.generate_structured(
                "", ClaimGenerationResult, task=TASK_CLAIM_GENERATION,
                context={"topic": topic, "evidence": payload, "product": product_name},
            )

        generated = list(result.claims)
        accepted_any = False
        for candidate in generated:
            statement = (candidate.statement or "").strip()
            if not statement:
                continue
            supporting_ids = [i for i in candidate.supporting_evidence_ids if i in valid_ids]
            contradicting_ids = [i for i in candidate.contradicting_evidence_ids if i in valid_ids]
            context_ids = [i for i in candidate.contextualizing_evidence_ids if i in valid_ids]

            cited_text = " ".join(
                evidence_by_id[i].text for i in supporting_ids + contradicting_ids + context_ids
            )
            if not _numbers(statement) <= _numbers(cited_text):
                # A number appears in the claim that no cited evidence contains.
                log.info("rejecting claim with ungrounded numbers on topic %s", topic)
                continue

            links = [
                ClaimEvidenceLink(evidence_id=i, relationship=Relationship.SUPPORTS)
                for i in supporting_ids
            ]
            links += [
                ClaimEvidenceLink(evidence_id=i, relationship=Relationship.CONTRADICTS)
                for i in contradicting_ids
            ]
            links += [
                ClaimEvidenceLink(evidence_id=i, relationship=Relationship.CONTEXTUALIZES)
                for i in context_ids
            ]
            if not links:
                continue

            supporting = [evidence_by_id[i] for i in supporting_ids]
            contradicting = [evidence_by_id[i] for i in contradicting_ids]
            claims.append(
                Claim(
                    research_job_id=ctx.job_id,
                    topic=topic,
                    statement=statement,
                    status=_initial_status(supporting, contradicting, source_by_id),
                    confidence=0.0,
                    links=links,
                )
            )
            accepted_any = True

        if not accepted_any:
            limitations.append(
                f"No usable claim could be generated for '{topic}'; its evidence is still listed."
            )

        conflict = await _detect_conflict(ctx, topic, topic_evidence, source_by_id)
        if conflict is not None:
            conflicts.append(conflict)

    await ctx.backend.post_claims(ctx.job_id, claims)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.CLAIMS_GENERATED,
        f"Generated {len(claims)} claim(s) across {len(by_topic)} topic(s); "
        f"{len(conflicts)} conflict(s) detected.",
        {
            "claimCount": len(claims),
            "conflictCount": len(conflicts),
            "conflictTopics": [conflict.topic for conflict in conflicts],
        },
    )

    return {"claims": claims, "conflicts": conflicts, "limitations": limitations}


async def _detect_conflict(
    ctx: JobContext,
    topic: str,
    topic_evidence: list[Evidence],
    source_by_id: dict[str, Source],
) -> Conflict | None:
    positive = [e for e in topic_evidence if e.sentiment == Sentiment.POSITIVE]
    negative = [e for e in topic_evidence if e.sentiment == Sentiment.NEGATIVE]
    if not positive or not negative:
        return None

    positive_groups = _groups_for(positive, source_by_id)
    negative_groups = _groups_for(negative, source_by_id)

    if not is_genuine_conflict(
        positive_groups,
        negative_groups,
        positive_has_strong=_has_strong(positive),
        negative_has_strong=_has_strong(negative),
    ):
        return None

    positive_texts = [item.text for item in positive]
    negative_texts = [item.text for item in negative]

    try:
        explanation = await ctx.llm.generate_structured(
            conflict_explanation_prompt(topic, positive_texts, negative_texts),
            ConflictExplanation,
            task=TASK_CONFLICT_EXPLANATION,
            context={
                "topic": topic,
                "positive_texts": positive_texts,
                "negative_texts": negative_texts,
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("conflict explanation failed for %s: %s", topic, exc)
        explanation = ConflictExplanation(
            explanation=(
                f"Sources disagree about {topic}; both positions are preserved because the "
                f"available evidence does not settle the disagreement."
            ),
            resolved=False,
        )

    positive_context = dominant_qualifiers(positive_texts)
    negative_context = dominant_qualifiers(negative_texts)

    return Conflict(
        topic=topic,
        position_a=ConflictPosition(
            text=(
                f"Reported as good in the context of {positive_context}."
                if positive_context
                else f"Reported positively for {topic}."
            ),
            evidence_ids=[item.id for item in positive],
        ),
        position_b=ConflictPosition(
            text=(
                f"Reported as a problem in the context of {negative_context}."
                if negative_context
                else f"Reported negatively for {topic}."
            ),
            evidence_ids=[item.id for item in negative],
        ),
        explanation=explanation.explanation.strip()
        or f"Sources disagree about {topic}; both positions are preserved.",
        resolved=False,
    )
