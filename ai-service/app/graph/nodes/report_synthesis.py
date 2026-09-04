"""Node 9 — report synthesis.

The numbers come first and they are all derived: category scores from evidence
quality and independence, the overall score from a neutral (equal-weight) mean of
those category scores, and confidence from independence, strength, agreement and
recency. Only the prose is generated, and it is checked for numbers the data does
not contain before it is accepted.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

from app.graph.context import JobContext
from app.graph.prompts import narrative_prompt
from app.graph.schemas import NarrativeSummary
from app.graph.state import ResearchState
from app.models.domain import (
    CategoryScore,
    Claim,
    Conflict,
    Evidence,
    EvidenceBackedText,
    FindingRef,
    Report,
    ReportClaim,
    ReportEvidenceRef,
    ReportSection,
    ReportSourceRef,
    Source,
)
from app.models.enums import (
    ClaimStatus,
    ErrorCode,
    EventType,
    JobStatus,
    Relationship,
    SectionType,
    Sentiment,
    SourceStatus,
)
from app.providers.llm import TASK_NARRATIVE, MockLLMProvider
from app.services import scoring

log = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

STRENGTH_SCORE_FLOOR = 60
WEAKNESS_SCORE_CEILING = 45
LONG_TERM_TOPIC = "Reliability & Longevity"
MAX_LIST_ITEMS = 5
MAX_EVIDENCE_PER_ITEM = 4

DEMO_CAVEAT = (
    "DEMO MODE: this report was produced from Proofly's deterministic local fixture dataset. "
    "The sources listed are labelled demo fixtures on a reserved, non-resolvable domain — they "
    "are not live web, Reddit or YouTube results."
)


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER_RE.finditer(text)}


async def report_synthesis_node(ctx: JobContext, state: ResearchState) -> dict:
    await ctx.backend.post_status(ctx.job_id, JobStatus.GENERATING_REPORT)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.REPORT_GENERATION_STARTED,
        "Synthesising the final report.",
        {"claimCount": len(state.get("claims", []))},
    )

    sources: list[Source] = list(state.get("sources", []))
    evidence: list[Evidence] = list(state.get("evidence", []))
    claims: list[Claim] = list(state.get("claims", []))
    conflicts: list[Conflict] = list(state.get("conflicts", []))
    limitations: list[str] = list(state.get("limitations", []))
    channel_outcomes: dict = dict(state.get("channel_outcomes", {}))
    product = state["product"]
    plan = state.get("plan")
    product_name = product.canonical_name or product.raw_query

    fetched_sources = [source for source in sources if source.status == SourceStatus.FETCHED]
    source_by_id = {source.id: source for source in sources}
    evidence_by_id = {item.id: item for item in evidence}

    if not fetched_sources:
        message = (
            f"No sources could be retrieved for {product_name!r}, so no evidence-backed report "
            f"can be produced."
        )
        await ctx.backend.post_event(
            ctx.job_id,
            EventType.JOB_FAILED,
            message,
            {"errorCode": ErrorCode.INSUFFICIENT_DATA.value, "limitations": limitations},
        )
        await ctx.backend.post_status(
            ctx.job_id,
            JobStatus.FAILED,
            current_stage=JobStatus.GENERATING_REPORT.value,
            error_code=ErrorCode.INSUFFICIENT_DATA.value,
            error_message=message,
        )
        return {
            "report": None,
            "sections": [],
            "terminal_status": JobStatus.FAILED.value,
            "error_code": ErrorCode.INSUFFICIENT_DATA.value,
            "error_message": message,
        }

    today = date.today()
    topic_scores = scoring.score_topics(evidence, source_by_id, today=today)
    independent_groups = {
        source.independence_group_id or source.id for source in fetched_sources
    }
    failed_channels = [
        name for name, outcome in channel_outcomes.items() if outcome.get("status") == "FAILED"
    ]
    degraded = bool(ctx.budget.degradations)

    score = scoring.overall_score(topic_scores)
    confidence = scoring.overall_confidence(
        topic_scores,
        failed_channels=len(failed_channels),
        independent_group_count=len(independent_groups),
        degraded=degraded,
    )
    verdict = scoring.verdict_for(score, confidence, bool(evidence))

    category_scores = [
        CategoryScore(category=item.topic, score=item.score, confidence=item.confidence)
        for item in topic_scores
    ]

    strengths = _evidence_backed(
        [item for item in sorted(topic_scores, key=lambda s: -s.score) if item.score >= STRENGTH_SCORE_FLOOR],
        positive=True,
    )
    weaknesses = _evidence_backed(
        [item for item in sorted(topic_scores, key=lambda s: s.score) if item.score <= WEAKNESS_SCORE_CEILING],
        positive=False,
    )
    praise = _common_sentiment(evidence, source_by_id, Sentiment.POSITIVE)
    complaints = _common_sentiment(evidence, source_by_id, Sentiment.NEGATIVE)

    findings = [
        FindingRef(text=claim.statement, claim_id=claim.id)
        for claim in sorted(claims, key=lambda c: -c.confidence)[:6]
    ]

    long_term = _long_term(evidence)
    who_should_buy, who_should_avoid = _audience_guidance(strengths, weaknesses, conflicts)

    caveats = _build_caveats(
        ctx, limitations, failed_channels, len(independent_groups), plan, evidence, conflicts
    )

    narrative_context = {
        "product": product_name,
        "demo_mode": ctx.demo_mode,
        "overall_score": score,
        "confidence": confidence,
        "verdict": verdict,
        "source_count": len(fetched_sources),
        "independent_group_count": len(independent_groups),
        "strengths": [item.category for item in category_scores if item.score >= STRENGTH_SCORE_FLOOR],
        "weaknesses": [item.category for item in category_scores if item.score <= WEAKNESS_SCORE_CEILING],
        "conflict_topics": [conflict.topic for conflict in conflicts],
        "who_should_buy": who_should_buy,
        "who_should_avoid": who_should_avoid,
        "category_scores": [
            {"category": item.category, "score": item.score, "confidence": item.confidence}
            for item in category_scores
        ],
    }
    executive_summary = await _executive_summary(ctx, narrative_context)

    report = Report(
        research_job_id=ctx.job_id,
        demo_mode=ctx.demo_mode,
        overall_score=score,
        verdict=verdict,
        confidence=confidence,
        executive_summary=executive_summary,
        category_scores=category_scores,
        key_strengths=strengths,
        key_weaknesses=weaknesses,
        key_findings=findings,
        common_praise=praise,
        common_complaints=complaints,
        conflicts=conflicts,
        long_term_ownership=long_term,
        who_should_buy=who_should_buy,
        who_should_avoid=who_should_avoid,
        caveats=caveats,
        sources=[
            ReportSourceRef(
                id=source.id,
                url=source.url,
                title=source.title,
                source_type=source.source_type.value,
                channel=source.channel.value,
            )
            for source in fetched_sources
        ],
        claims=[_report_claim(claim, evidence_by_id) for claim in claims],
    )

    sections = _build_sections(report)

    await ctx.backend.post_report(ctx.job_id, report, sections)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.REPORT_COMPLETED,
        f"Report ready: {verdict} ({score}/100, confidence {confidence:.2f}).",
        {
            "overallScore": score,
            "confidence": confidence,
            "verdict": verdict,
            "claimCount": len(report.claims),
            "conflictCount": len(conflicts),
            "sourceCount": len(fetched_sources),
        },
    )

    partial = bool(failed_channels) or degraded or not evidence
    terminal = JobStatus.PARTIALLY_COMPLETED if partial else JobStatus.COMPLETED
    if partial:
        await ctx.backend.post_event(
            ctx.job_id,
            EventType.JOB_PARTIALLY_COMPLETED,
            "The job completed with limitations; see the report caveats.",
            {"failedChannels": failed_channels, "degradations": ctx.budget.degradations},
        )
    await ctx.backend.post_status(ctx.job_id, terminal, current_stage=terminal.value)

    return {"report": report, "sections": sections, "terminal_status": terminal.value}


# ───────────────────────────── helpers ─────────────────────────────────────


def _evidence_backed(topic_scores, *, positive: bool) -> list[EvidenceBackedText]:
    items: list[EvidenceBackedText] = []
    for score in topic_scores[:MAX_LIST_ITEMS]:
        ids = score.positive_evidence_ids if positive else score.negative_evidence_ids
        if not ids:
            continue
        direction = "strength" if positive else "weakness"
        items.append(
            EvidenceBackedText(
                text=(
                    f"{score.topic} is a {direction}: scored {score.score}/100 from "
                    f"{score.evidence_count} piece(s) of evidence across {score.group_count} "
                    f"independent source group(s)."
                ),
                evidence_ids=ids[:MAX_EVIDENCE_PER_ITEM],
            )
        )
    return items


def _common_sentiment(
    evidence: list[Evidence], source_by_id: dict[str, Source], sentiment: Sentiment
) -> list[EvidenceBackedText]:
    buckets: dict[str, list[Evidence]] = {}
    for item in evidence:
        if item.sentiment == sentiment:
            buckets.setdefault(item.topic, []).append(item)

    results: list[EvidenceBackedText] = []
    for topic, items in buckets.items():
        groups = {scoring.group_of(item, source_by_id) for item in items}
        if len(groups) < 2:
            # A single voice is not a "common" praise or complaint.
            continue
        word = "praised" if sentiment == Sentiment.POSITIVE else "criticised"
        results.append(
            EvidenceBackedText(
                text=(
                    f"{topic} is {word} by {len(groups)} independent source group(s) "
                    f"({len(items)} mentions)."
                ),
                evidence_ids=[item.id for item in items][:MAX_EVIDENCE_PER_ITEM],
            )
        )
    results.sort(key=lambda item: item.text)
    return results[:MAX_LIST_ITEMS]


def _long_term(evidence: list[Evidence]) -> EvidenceBackedText:
    items = [item for item in evidence if item.topic == LONG_TERM_TOPIC]
    if not items:
        return EvidenceBackedText(
            text=(
                "No long-term ownership evidence was found in the sources gathered for this job."
            ),
            evidence_ids=[],
        )
    positive = sum(1 for item in items if item.sentiment == Sentiment.POSITIVE)
    negative = sum(1 for item in items if item.sentiment == Sentiment.NEGATIVE)
    return EvidenceBackedText(
        text=(
            f"Long-term ownership evidence: {len(items)} report(s), of which {positive} positive "
            f"and {negative} negative. See the cited evidence for the specific accounts."
        ),
        evidence_ids=[item.id for item in items][:MAX_EVIDENCE_PER_ITEM],
    )


def _audience_guidance(
    strengths: list[EvidenceBackedText],
    weaknesses: list[EvidenceBackedText],
    conflicts: list[Conflict],
) -> tuple[list[str], list[str]]:
    def topic_of(item: EvidenceBackedText) -> str:
        return item.text.split(" is a ")[0]

    buy = [
        f"Buyers who prioritise {topic_of(item)}, where the evidence is consistently positive."
        for item in strengths[:3]
    ]
    avoid = [
        f"Buyers who depend on {topic_of(item)}, where the evidence is consistently negative."
        for item in weaknesses[:3]
    ]
    for conflict in conflicts[:2]:
        avoid.append(
            f"Buyers who need dependable {conflict.topic} in every situation: sources disagree, "
            f"and the outcome appears to depend on context."
        )
    if not buy:
        buy.append(
            "No audience can be recommended with confidence from the evidence gathered."
        )
    if not avoid:
        avoid.append(
            "No group can be identified as clearly ill-served by this product from the evidence "
            "gathered."
        )
    return buy, avoid


def _build_caveats(
    ctx: JobContext,
    limitations: list[str],
    failed_channels: list[str],
    group_count: int,
    plan,
    evidence: list[Evidence],
    conflicts: list[Conflict],
) -> list[str]:
    caveats: list[str] = []
    if ctx.demo_mode:
        caveats.append(DEMO_CAVEAT)
    for note in ctx.providers.notes:
        if note not in caveats:
            caveats.append(note)
    for channel in failed_channels:
        caveats.append(
            f"{channel} research was unavailable for this run, so the report draws on fewer "
            f"channels than planned."
        )
    for limitation in limitations:
        if limitation not in caveats:
            caveats.append(limitation)
    for note in ctx.budget.notes:
        if note not in caveats:
            caveats.append(note)
    if group_count < 3:
        caveats.append(
            f"Only {group_count} independent source group(s) were found; confidence is reduced "
            f"accordingly."
        )
    if plan is not None and not plan.category_matched:
        caveats.append(
            "The product category was not recognised, so generic research dimensions were used."
        )
    if not evidence:
        caveats.append("No evidence could be extracted, so no claim in this report is supported.")
    if conflicts:
        caveats.append(
            f"{len(conflicts)} unresolved conflict(s) between sources are reported as-is rather "
            f"than averaged into a single answer."
        )
    if ctx.backend.failures:
        caveats.append(
            f"{len(ctx.backend.failures)} progress callback(s) to the backend failed during this "
            f"run; the report content itself is unaffected."
        )
    return caveats


async def _executive_summary(ctx: JobContext, context: dict) -> str:
    fallback_provider = MockLLMProvider()
    deterministic = await fallback_provider.generate_structured(
        "", NarrativeSummary, task=TASK_NARRATIVE, context=context
    )
    try:
        generated = await ctx.llm.generate_structured(
            narrative_prompt(context), NarrativeSummary, task=TASK_NARRATIVE, context=context
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("narrative generation failed: %s", exc)
        return deterministic.executive_summary

    summary = (generated.executive_summary or "").strip()
    if not summary:
        return deterministic.executive_summary

    permitted = _numbers(json.dumps(context, default=str))
    used = _numbers(summary)
    if not used <= permitted:
        log.info(
            "rejecting generated summary: contains numbers not present in the computed data (%s)",
            sorted(used - permitted),
        )
        return deterministic.executive_summary
    if ctx.demo_mode and "demo" not in summary.lower():
        summary = f"{DEMO_CAVEAT} {summary}"
    return summary


def _report_claim(claim: Claim, evidence_by_id: dict[str, Evidence]) -> ReportClaim:
    def refs(relationship: Relationship) -> list[ReportEvidenceRef]:
        return [
            ReportEvidenceRef(
                id=item.id,
                text=item.text,
                source_id=item.source_id,
            )
            for item in (
                evidence_by_id.get(link.evidence_id)
                for link in claim.links
                if link.relationship == relationship
            )
            if item is not None
        ]

    supporting = refs(Relationship.SUPPORTS)
    if claim.status != ClaimStatus.INSUFFICIENT_EVIDENCE:
        supporting = supporting + refs(Relationship.CONTEXTUALIZES)

    return ReportClaim(
        id=claim.id,
        topic=claim.topic,
        statement=claim.statement,
        status=claim.status.value,
        confidence=round(claim.confidence, 4),
        supporting_evidence=supporting,
        contradicting_evidence=refs(Relationship.CONTRADICTS),
    )


def _build_sections(report: Report) -> list[ReportSection]:
    def dump(items) -> list:
        return [item.model_dump(by_alias=True, mode="json") for item in items]

    definitions: list[tuple[SectionType, str, dict]] = [
        (
            SectionType.EXECUTIVE_SUMMARY,
            "Executive summary",
            {
                "summary": report.executive_summary,
                "verdict": report.verdict,
                "overallScore": report.overall_score,
                "confidence": report.confidence,
                "demoMode": report.demo_mode,
            },
        ),
        (
            SectionType.CATEGORY_ANALYSIS,
            "Category analysis",
            {"categoryScores": dump(report.category_scores)},
        ),
        (SectionType.STRENGTHS, "Key strengths", {"items": dump(report.key_strengths)}),
        (SectionType.WEAKNESSES, "Key weaknesses", {"items": dump(report.key_weaknesses)}),
        (SectionType.KEY_FINDINGS, "Key findings", {"items": dump(report.key_findings)}),
        (SectionType.COMMON_PRAISE, "Common praise", {"items": dump(report.common_praise)}),
        (
            SectionType.COMMON_COMPLAINTS,
            "Common complaints",
            {"items": dump(report.common_complaints)},
        ),
        (SectionType.CONFLICTS, "Conflicting evidence", {"items": dump(report.conflicts)}),
        (
            SectionType.LONG_TERM_OWNERSHIP,
            "Long-term ownership",
            report.long_term_ownership.model_dump(by_alias=True, mode="json")
            if report.long_term_ownership
            else {"text": "", "evidenceIds": []},
        ),
        (SectionType.WHO_SHOULD_BUY, "Who should buy", {"items": report.who_should_buy}),
        (SectionType.WHO_SHOULD_AVOID, "Who should avoid", {"items": report.who_should_avoid}),
        (SectionType.CAVEATS, "Caveats and limitations", {"items": report.caveats}),
        (SectionType.SOURCES, "Sources", {"items": dump(report.sources)}),
    ]
    return [
        ReportSection(section_type=section_type, title=title, content=content, order_index=index)
        for index, (section_type, title, content) in enumerate(definitions)
    ]
