"""Deterministic scoring.

Scores and confidences are *computed*, never asked of a language model. The
inputs are evidence quality (strength), source authority, source independence,
agreement between independent groups, and recency. Duplicate or syndicated
sources cannot raise a score because each independence group votes once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.domain import Claim, Evidence, Source
from app.models.enums import ClaimStatus, Relationship, Sentiment, Strength

STRENGTH_WEIGHT: dict[Strength, float] = {
    Strength.STRONG: 1.0,
    Strength.MODERATE: 0.65,
    Strength.WEAK: 0.3,
}

POLARITY: dict[Sentiment, float] = {
    Sentiment.POSITIVE: 1.0,
    Sentiment.NEGATIVE: -1.0,
    Sentiment.MIXED: 0.0,
    Sentiment.NEUTRAL: 0.0,
}

RECENCY_WINDOW_MONTHS = 24
UNKNOWN_DATE_RECENCY = 0.5

# Confidence weighting — independence dominates, exactly as the product rules
# require ("low/duplicate/dependent evidence → low confidence").
W_INDEPENDENCE = 0.40
W_STRENGTH = 0.25
W_AGREEMENT = 0.20
W_RECENCY = 0.15


@dataclass
class TopicScore:
    topic: str
    score: int
    confidence: float
    evidence_count: int
    group_count: int
    positive_evidence_ids: list[str] = field(default_factory=list)
    negative_evidence_ids: list[str] = field(default_factory=list)
    neutral_evidence_ids: list[str] = field(default_factory=list)


def group_of(evidence: Evidence, source_by_id: dict[str, Source]) -> str:
    source = source_by_id.get(evidence.source_id)
    return (source.independence_group_id if source else None) or evidence.source_id


def evidence_weight(evidence: Evidence, source_by_id: dict[str, Source]) -> float:
    source = source_by_id.get(evidence.source_id)
    authority = source.authority_score if source else 0.5
    return STRENGTH_WEIGHT.get(evidence.strength, 0.5) * max(authority, 0.05)


def _recency(evidence: list[Evidence], source_by_id: dict[str, Source], today: date) -> float:
    if not evidence:
        return UNKNOWN_DATE_RECENCY
    scores: list[float] = []
    for item in evidence:
        source = source_by_id.get(item.source_id)
        published = source.published_at if source else None
        if published is None:
            scores.append(UNKNOWN_DATE_RECENCY)
            continue
        months = (today.year - published.year) * 12 + (today.month - published.month)
        if months <= RECENCY_WINDOW_MONTHS:
            scores.append(1.0)
        elif months <= RECENCY_WINDOW_MONTHS * 2:
            scores.append(0.5)
        else:
            scores.append(0.15)
    return sum(scores) / len(scores)


def _agreement(positive_weight: float, negative_weight: float) -> float:
    total = positive_weight + negative_weight
    if total <= 0:
        return 0.5
    minority = min(positive_weight, negative_weight)
    return max(0.0, 1.0 - (2 * minority / total))


def score_topic(
    topic: str,
    evidence: list[Evidence],
    source_by_id: dict[str, Source],
    *,
    today: date | None = None,
) -> TopicScore | None:
    today = today or date.today()
    evaluative = [
        item for item in evidence if item.sentiment in (Sentiment.POSITIVE, Sentiment.NEGATIVE, Sentiment.MIXED)
    ]
    groups: dict[str, list[Evidence]] = {}
    for item in evidence:
        groups.setdefault(group_of(item, source_by_id), []).append(item)

    if not evaluative:
        return None
    evaluative_ids = {item.id for item in evaluative}

    # One vote per independence group: the group's polarity is the weighted mean
    # of its own evidence, and the group's weight is its single best piece.
    group_polarity: list[tuple[float, float]] = []
    positive_weight = 0.0
    negative_weight = 0.0
    for members in groups.values():
        members_eval = [item for item in members if item.id in evaluative_ids]
        if not members_eval:
            continue
        weights = [evidence_weight(item, source_by_id) for item in members_eval]
        polarity_sum = sum(
            POLARITY[item.sentiment] * weight
            for item, weight in zip(members_eval, weights, strict=False)
        )
        weight_sum = sum(weights) or 1.0
        polarity = polarity_sum / weight_sum
        group_weight = max(weights)
        group_polarity.append((polarity, group_weight))
        if polarity > 0:
            positive_weight += group_weight * polarity
        elif polarity < 0:
            negative_weight += group_weight * -polarity

    if not group_polarity:
        return None

    total_weight = sum(weight for _, weight in group_polarity) or 1.0
    weighted_polarity = sum(polarity * weight for polarity, weight in group_polarity) / total_weight
    score = int(round(max(0.0, min(100.0, 50.0 + 50.0 * weighted_polarity))))

    group_count = len(groups)
    independence_factor = min(1.0, group_count / 3.0)
    strength_factor = (
        sum(STRENGTH_WEIGHT.get(item.strength, 0.5) for item in evidence) / len(evidence)
    )
    agreement = _agreement(positive_weight, negative_weight)
    recency = _recency(evidence, source_by_id, today)

    confidence = (
        W_INDEPENDENCE * independence_factor
        + W_STRENGTH * strength_factor
        + W_AGREEMENT * agreement
        + W_RECENCY * recency
    )

    return TopicScore(
        topic=topic,
        score=score,
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        evidence_count=len(evidence),
        group_count=group_count,
        positive_evidence_ids=[i.id for i in evidence if i.sentiment == Sentiment.POSITIVE],
        negative_evidence_ids=[i.id for i in evidence if i.sentiment == Sentiment.NEGATIVE],
        neutral_evidence_ids=[
            i.id for i in evidence if i.sentiment in (Sentiment.NEUTRAL, Sentiment.MIXED)
        ],
    )


def score_topics(
    evidence: list[Evidence],
    source_by_id: dict[str, Source],
    *,
    today: date | None = None,
) -> list[TopicScore]:
    by_topic: dict[str, list[Evidence]] = {}
    for item in evidence:
        by_topic.setdefault(item.topic, []).append(item)
    scores = []
    for topic in sorted(by_topic):
        score = score_topic(topic, by_topic[topic], source_by_id, today=today)
        if score is not None:
            scores.append(score)
    return scores


def overall_score(topic_scores: list[TopicScore]) -> int:
    """Neutral default weights: every scored dimension counts the same."""

    if not topic_scores:
        return 0
    return int(round(sum(score.score for score in topic_scores) / len(topic_scores)))


def overall_confidence(
    topic_scores: list[TopicScore],
    *,
    failed_channels: int = 0,
    independent_group_count: int = 0,
    degraded: bool = False,
) -> float:
    if not topic_scores:
        return 0.0
    base = sum(score.confidence for score in topic_scores) / len(topic_scores)
    for _ in range(max(0, failed_channels)):
        base *= 0.85
    if independent_group_count < 3:
        base *= 0.9
    if degraded:
        base *= 0.95
    return round(max(0.0, min(1.0, base)), 3)


def verdict_for(score: int, confidence: float, has_evidence: bool) -> str:
    if not has_evidence:
        return "Insufficient evidence to reach a verdict"
    if confidence < 0.35:
        return "Insufficient evidence for a confident verdict"
    if score >= 80:
        return "Recommended"
    if score >= 65:
        return "Recommended with caveats"
    if score >= 50:
        return "Mixed — depends on your priorities"
    if score >= 35:
        return "Not recommended for most buyers"
    return "Not recommended"


def claim_confidence(
    claim: Claim,
    evidence_by_id: dict[str, Evidence],
    source_by_id: dict[str, Source],
    *,
    today: date | None = None,
) -> float:
    supporting = [
        evidence_by_id[link.evidence_id]
        for link in claim.links
        if link.relationship == Relationship.SUPPORTS and link.evidence_id in evidence_by_id
    ]
    contradicting = [
        evidence_by_id[link.evidence_id]
        for link in claim.links
        if link.relationship == Relationship.CONTRADICTS and link.evidence_id in evidence_by_id
    ]
    related = supporting + contradicting
    if not related:
        return 0.0

    groups = {group_of(item, source_by_id) for item in related}
    independence_factor = min(1.0, len(groups) / 3.0)
    strength_factor = sum(STRENGTH_WEIGHT.get(i.strength, 0.5) for i in related) / len(related)
    supporting_weight = sum(evidence_weight(i, source_by_id) for i in supporting)
    contradicting_weight = sum(evidence_weight(i, source_by_id) for i in contradicting)
    agreement = _agreement(supporting_weight, contradicting_weight)
    recency = _recency(related, source_by_id, today or date.today())

    confidence = (
        W_INDEPENDENCE * independence_factor
        + W_STRENGTH * strength_factor
        + W_AGREEMENT * agreement
        + W_RECENCY * recency
    )

    ceiling = {
        ClaimStatus.SUPPORTED: 1.0,
        ClaimStatus.PARTIALLY_SUPPORTED: 0.6,
        ClaimStatus.CONTESTED: 0.5,
        ClaimStatus.INSUFFICIENT_EVIDENCE: 0.25,
    }[claim.status]
    return round(max(0.0, min(ceiling, confidence)), 3)
