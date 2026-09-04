"""Hand-built pipeline state for focused node tests.

Small and explicit, so a test can assert exactly why a claim was downgraded or a
conflict was (or was not) raised, without depending on the whole golden run.
"""

from __future__ import annotations

from datetime import date

from app.graph.state import initial_state
from app.models.domain import (
    Evidence,
    ProductResolution,
    ResearchDimension,
    ResearchPlan,
    Source,
)
from app.models.enums import (
    Channel,
    EvidenceType,
    Sentiment,
    SourceStatus,
    SourceType,
    Strength,
)

PRODUCT = ProductResolution(
    raw_query="Sony WH-1000XM6",
    canonical_name="Sony WH-1000XM6",
    brand="Sony",
    model="WH-1000XM6",
    category="headphones",
    resolution_confidence=0.95,
)

PLAN = ResearchPlan(
    category="headphones",
    category_matched=True,
    dimensions=[
        ResearchDimension(name="Sound Quality", rationale="r"),
        ResearchDimension(name="Battery Life", rationale="r"),
        ResearchDimension(name="Microphone & Call Quality", rationale="r"),
        ResearchDimension(name="Build Quality", rationale="r", universal=True),
    ],
    web_queries=["Sony WH-1000XM6 review"],
    reddit_queries=["Sony WH-1000XM6 review"],
    youtube_queries=["Sony WH-1000XM6 review"],
)


def _source(
    index: int,
    *,
    channel: Channel = Channel.WEB,
    source_type: SourceType = SourceType.PROFESSIONAL_REVIEW,
    authority: float = 0.8,
    group: str | None = None,
    published: date = date(2025, 6, 1),
) -> Source:
    source = Source(
        id=f"source-{index}",
        channel=channel,
        url=f"https://fixtures.proofly.invalid/web/publisher-{index}/page",
        title=f"Test source {index}",
        source_type=source_type,
        authority_score=authority,
        first_hand=True,
        status=SourceStatus.FETCHED,
        published_at=published,
        raw_text=f"body of source {index}",
    )
    source.independence_group_id = group or f"group-{index}"
    return source


def build_sources() -> list[Source]:
    return [
        _source(1),
        _source(2),
        _source(3, channel=Channel.YOUTUBE, source_type=SourceType.VIDEO_REVIEW, authority=0.65),
        _source(4, channel=Channel.REDDIT, source_type=SourceType.FORUM_POST, authority=0.45),
        _source(5, channel=Channel.REDDIT, source_type=SourceType.FORUM_POST, authority=0.45),
        # Source 6 is a syndicated copy of source 1: same independence group.
        _source(6, source_type=SourceType.GENERIC, authority=0.45, group="group-1"),
    ]


def build_evidence(job_id: str) -> list[Evidence]:
    def item(
        index: int,
        source_index: int,
        topic: str,
        sentiment: Sentiment,
        text: str,
        *,
        evidence_type: EvidenceType = EvidenceType.EXPERT_OPINION,
        strength: Strength = Strength.MODERATE,
    ) -> Evidence:
        return Evidence(
            id=f"evidence-{index}",
            research_job_id=job_id,
            source_id=f"source-{source_index}",
            passage_id=f"passage-{index}",
            topic=topic,
            sentiment=sentiment,
            evidence_type=evidence_type,
            strength=strength,
            text=text,
        )

    mic = "Microphone & Call Quality"
    return [
        # A genuine, context-dependent conflict: three independent groups on each side.
        item(1, 1, mic, Sentiment.POSITIVE, "In a quiet indoor room the microphone is clean and intelligible."),
        item(2, 2, mic, Sentiment.POSITIVE, "Indoors the microphone is perfectly good on work calls from the office."),
        item(3, 4, mic, Sentiment.POSITIVE, "I take calls from my home office and nobody complains about the mic.",
             evidence_type=EvidenceType.CUSTOMER_EXPERIENCE),
        item(4, 3, mic, Sentiment.NEGATIVE, "Recorded outside on a windy afternoon the wind overwhelms it and my voice is muffled."),
        item(5, 5, mic, Sentiment.NEGATIVE, "The moment I walk outside on a windy day callers say my voice is breaking up.",
             evidence_type=EvidenceType.CUSTOMER_EXPERIENCE),
        item(6, 2, mic, Sentiment.NEGATIVE, "In our wind tunnel test the microphone degraded badly and became unintelligible.",
             evidence_type=EvidenceType.MEASUREMENT, strength=Strength.STRONG),
        # Battery: broad agreement plus a single dissenting report (an outlier, not a conflict).
        item(7, 1, "Battery Life", Sentiment.POSITIVE, "Battery life is excellent and matched the claim in our test."),
        item(8, 2, "Battery Life", Sentiment.POSITIVE, "Battery life in normal mixed use was great over the week."),
        item(9, 4, "Battery Life", Sentiment.POSITIVE, "Battery life is great for me, easily a full week of commuting.",
             evidence_type=EvidenceType.CUSTOMER_EXPERIENCE),
        item(10, 5, "Battery Life", Sentiment.NEGATIVE, "My battery life is poor and drains far quicker than expected.",
             evidence_type=EvidenceType.ANECDOTE, strength=Strength.WEAK),
        # Sound quality: unanimous across two independent groups.
        item(11, 1, "Sound Quality", Sentiment.POSITIVE, "Sound quality is excellent for the category and well tuned."),
        item(12, 3, "Sound Quality", Sentiment.POSITIVE, "Sound quality out of the box is warm and controlled, genuinely good."),
        # Build quality: one weak anecdote from one source only.
        item(13, 5, "Build Quality", Sentiment.NEGATIVE, "My left hinge has started creaking, a bad build quality problem.",
             evidence_type=EvidenceType.ANECDOTE, strength=Strength.WEAK),
    ]


def build_analysis_state(job_id: str) -> dict:
    state = initial_state(job_id, "Sony WH-1000XM6", True)
    state["product"] = PRODUCT
    state["plan"] = PLAN
    state["sources"] = build_sources()
    state["evidence"] = build_evidence(job_id)
    state["channel_outcomes"] = {
        "WEB": {"status": "OK", "sources": 3, "error": ""},
        "REDDIT": {"status": "OK", "sources": 2, "error": ""},
        "YOUTUBE": {"status": "OK", "sources": 1, "error": ""},
    }
    return state
