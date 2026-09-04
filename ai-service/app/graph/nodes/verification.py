"""Node 8 — verification.

Every claim is put through the same checklist before it is allowed into a report:

1. Does evidence exist for it at all?
2. Is that evidence actually about this topic?
3. Is the evidence credible (from a source we really fetched)?
4. Is it independent, or one voice repeated?
5. Is it contradicted by other evidence?
6. Is the claim worded more strongly than the evidence supports?
7. Is the evidence stale?
8. Is it one anecdote, or a pattern repeated across independent sources?
9. Is the wording appropriately cautious for its status?

Claims are downgraded or removed accordingly. Confidence is then computed from
evidence quality — never taken from the model.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from app.graph.context import JobContext
from app.graph.prompts import verification_prompt
from app.graph.schemas import VerificationResult
from app.graph.state import ResearchState
from app.models.domain import Claim, Evidence, Source
from app.models.enums import (
    ClaimStatus,
    EventType,
    EvidenceType,
    JobStatus,
    Relationship,
    SourceStatus,
    Strength,
)
from app.providers.llm import TASK_VERIFICATION
from app.services import scoring
from app.services.conflict import is_genuine_conflict

log = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
STALE_MONTHS = 48

_DOWNGRADE = {
    ClaimStatus.SUPPORTED: ClaimStatus.PARTIALLY_SUPPORTED,
    ClaimStatus.PARTIALLY_SUPPORTED: ClaimStatus.INSUFFICIENT_EVIDENCE,
    ClaimStatus.CONTESTED: ClaimStatus.CONTESTED,
    ClaimStatus.INSUFFICIENT_EVIDENCE: ClaimStatus.INSUFFICIENT_EVIDENCE,
}

CAUTIOUS_PREFIX = {
    ClaimStatus.PARTIALLY_SUPPORTED: "Partially supported: ",
    ClaimStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence: ",
    ClaimStatus.CONTESTED: "Contested: ",
}


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER_RE.finditer(text)}


def _months_old(published: date | None, today: date) -> int | None:
    if published is None:
        return None
    return (today.year - published.year) * 12 + (today.month - published.month)


async def verification_node(ctx: JobContext, state: ResearchState) -> dict:
    ctx.budget.check_deadline()
    await ctx.backend.post_status(ctx.job_id, JobStatus.VERIFYING)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.VERIFICATION_STARTED,
        "Verifying claims against their evidence.",
        {"claimCount": len(state.get("claims", []))},
    )

    claims: list[Claim] = list(state.get("claims", []))
    evidence: list[Evidence] = list(state.get("evidence", []))
    sources: list[Source] = list(state.get("sources", []))
    evidence_by_id = {item.id: item for item in evidence}
    source_by_id = {source.id: source for source in sources}
    product = state["product"]
    product_name = product.canonical_name or product.raw_query
    today = date.today()

    overstated_ids = await _llm_overstatement_check(ctx, product_name, claims, evidence_by_id)

    verified: list[Claim] = []
    removed = 0
    limitations: list[str] = []

    for claim in claims:
        notes: list[str] = []

        # 2 + 3: relevance and credibility filtering of the evidence links.
        surviving = []
        for link in claim.links:
            item = evidence_by_id.get(link.evidence_id)
            if item is None:
                notes.append("Dropped a reference to evidence that does not exist.")
                continue
            if item.topic != claim.topic:
                notes.append(
                    f"Dropped evidence {item.id} because it is about '{item.topic}', not "
                    f"'{claim.topic}'."
                )
                continue
            source = source_by_id.get(item.source_id)
            if source is None or source.status != SourceStatus.FETCHED:
                notes.append(f"Dropped evidence {item.id} because its source was not retrieved.")
                continue
            surviving.append(link)
        claim.links = surviving

        # 1: no surviving evidence means the claim is not grounded at all.
        if not claim.links:
            removed += 1
            log.info("removing ungrounded claim on topic %s", claim.topic)
            continue

        supporting = [
            evidence_by_id[link.evidence_id]
            for link in claim.links
            if link.relationship == Relationship.SUPPORTS
        ]
        contradicting = [
            evidence_by_id[link.evidence_id]
            for link in claim.links
            if link.relationship == Relationship.CONTRADICTS
        ]

        status = claim.status
        related = supporting + contradicting
        groups = {scoring.group_of(item, source_by_id) for item in related}

        # 5: contradiction is preserved, never voted away. Substantial
        # disagreement makes the claim CONTESTED; a lone dissenting report is not
        # dropped either, it just stops the claim from being fully supported.
        if contradicting and supporting:
            supporting_groups = {scoring.group_of(item, source_by_id) for item in supporting}
            contradicting_groups = {scoring.group_of(item, source_by_id) for item in contradicting}
            if is_genuine_conflict(
                supporting_groups,
                contradicting_groups,
                positive_has_strong=any(i.strength == Strength.STRONG for i in supporting),
                negative_has_strong=any(i.strength == Strength.STRONG for i in contradicting),
            ):
                if status != ClaimStatus.CONTESTED:
                    notes.append("Marked contested: independent evidence contradicts this claim.")
                status = ClaimStatus.CONTESTED
            elif status == ClaimStatus.SUPPORTED:
                status = ClaimStatus.PARTIALLY_SUPPORTED
                notes.append(
                    "Downgraded: at least one source contradicts this claim, though not enough "
                    "independent sources to call it contested."
                )
        elif not supporting:
            status = ClaimStatus.INSUFFICIENT_EVIDENCE
            notes.append("No supporting evidence survived verification.")

        # 4: independence.
        if len(groups) < 2 and status == ClaimStatus.SUPPORTED:
            status = ClaimStatus.PARTIALLY_SUPPORTED
            notes.append(
                "Downgraded: all supporting evidence traces back to a single independent source "
                "group."
            )

        # 8: one anecdote is not a pattern.
        if supporting and all(
            item.evidence_type == EvidenceType.ANECDOTE or item.strength == Strength.WEAK
            for item in supporting
        ):
            if len(groups) < 2:
                status = ClaimStatus.INSUFFICIENT_EVIDENCE
                notes.append(
                    "Downgraded: rests on a single weak or anecdotal report rather than a pattern "
                    "repeated across independent sources."
                )
            elif status == ClaimStatus.SUPPORTED:
                status = ClaimStatus.PARTIALLY_SUPPORTED
                notes.append("Downgraded: supported only by weak or anecdotal evidence.")

        # 6: claim stronger than its evidence.
        cited_text = " ".join(evidence_by_id[link.evidence_id].text for link in claim.links)
        ungrounded_numbers = _numbers(claim.statement) - _numbers(cited_text)
        if ungrounded_numbers:
            status = _DOWNGRADE[status]
            notes.append(
                "Downgraded: the claim contains figures "
                f"({', '.join(sorted(ungrounded_numbers))}) that its evidence does not state."
            )
        if claim.id in overstated_ids:
            status = _DOWNGRADE[status]
            notes.extend(overstated_ids[claim.id])

        # 7: staleness.
        ages = [
            _months_old(source_by_id[item.source_id].published_at, today)
            for item in related
            if item.source_id in source_by_id
        ]
        known_ages = [age for age in ages if age is not None]
        if known_ages and min(known_ages) > STALE_MONTHS:
            notes.append(
                f"All supporting sources are more than {STALE_MONTHS // 12} years old; the claim "
                f"may no longer describe the current product."
            )
            if status == ClaimStatus.SUPPORTED:
                status = ClaimStatus.PARTIALLY_SUPPORTED

        claim.status = status
        claim.confidence = scoring.claim_confidence(
            claim, evidence_by_id, source_by_id, today=today
        )

        # 9: cautious wording for anything short of SUPPORTED.
        prefix = CAUTIOUS_PREFIX.get(status)
        if prefix and not claim.statement.startswith(prefix):
            claim.statement = prefix + claim.statement[0].lower() + claim.statement[1:]

        claim.verification_notes = notes
        verified.append(claim)

    if removed:
        limitations.append(
            f"{removed} generated claim(s) were removed during verification because no valid "
            f"evidence supported them."
        )

    await ctx.backend.post_claims(ctx.job_id, verified)
    supported = sum(
        1
        for claim in verified
        if claim.status in (ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED)
    )
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.VERIFICATION_COMPLETED,
        f"Verified {len(verified)} claim(s); {supported} survived as supported or partially "
        f"supported, {removed} removed.",
        {
            "claimCount": len(verified),
            "verifiedClaimCount": supported,
            "removedClaimCount": removed,
            "statusBreakdown": {
                status.value: sum(1 for claim in verified if claim.status == status)
                for status in ClaimStatus
            },
        },
    )

    return {"claims": verified, "limitations": limitations}


async def _llm_overstatement_check(
    ctx: JobContext,
    product_name: str,
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> dict[str, list[str]]:
    """Ask the model which claims read as stronger than their evidence.

    The model can only *flag*; it cannot promote a claim or add evidence.
    """

    if not claims:
        return {}
    payload = [
        {
            "id": claim.id,
            "topic": claim.topic,
            "statement": claim.statement,
            "evidence": [
                evidence_by_id[link.evidence_id].text
                for link in claim.links
                if link.evidence_id in evidence_by_id
            ],
        }
        for claim in claims
    ]
    try:
        result = await ctx.llm.generate_structured(
            verification_prompt(product_name, payload),
            VerificationResult,
            task=TASK_VERIFICATION,
            context={"claims": payload, "product": product_name},
        )
    except Exception as exc:  # noqa: BLE001 - deterministic checks still apply
        log.warning("verification LLM pass failed: %s", exc)
        return {}

    known_ids = {claim.id for claim in claims}
    flagged: dict[str, list[str]] = {}
    for verdict in result.verdicts:
        if verdict.claim_id not in known_ids or not verdict.overstated:
            continue
        issues = [issue.strip() for issue in verdict.issues if issue.strip()]
        flagged[verdict.claim_id] = issues or [
            "Downgraded: wording judged stronger than the cited evidence supports."
        ]
    return flagged
