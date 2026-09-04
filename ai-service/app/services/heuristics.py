"""Deterministic text analysis shared by the mock LLM provider and by the
grounding checks that police the live LLM provider.

None of this invents content: every function only *labels* or *measures* text
that was actually fetched from a source.
"""

from __future__ import annotations

import hashlib
import re

from app.graph.catalog import Dimension
from app.models.enums import Channel, EvidenceType, Sentiment, SourceType, Strength

_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# How far into a sentence a keyword still counts as "what this sentence is about".
LEAD_WINDOW = 30

POSITIVE_MARKERS: tuple[str, ...] = (
    "excellent", "great", "best", "good", "love", "loved", "impressive", "strongest",
    "outstanding", "improvement", "improved", "clear", "clean", "comfortable", "no complaints",
    "recommend", "enjoyable", "stable", "reliable", "solid", "well", "better", "genuinely",
    "smooth", "useful", "perfect", "fine", "praise", "as advertised", "deserves",
    "helps", "vanished", "removes", "above average", "worked",
)

# Words that flip the polarity of a marker that follows them ("no complaints",
# "never had a problem") or that follows them closely ("defects were rare").
PRE_NEGATORS: tuple[str, ...] = (
    "no ", "not ", "never ", "without ", "hardly ", "rarely ", "zero ", "n't ", "nobody ",
    "none ", "free of ", "avoided ",
)
POST_NEGATORS: tuple[str, ...] = (
    " were rare", " are rare", " was rare", " is rare", " rarely", " were uncommon",
    " at all", " whatsoever",
)

NEGATIVE_MARKERS: tuple[str, ...] = (
    "bad", "poor", "worse", "worst", "problem", "problems", "issue", "issues", "complaint",
    "complaints", "annoyance", "annoying", "fails", "failed", "failure", "broke", "broken",
    "creak", "creaking", "muffled", "unintelligible", "breaking up", "cutting out", "degraded",
    "expensive", "overpriced", "hard to justify", "hard to ignore", "short", "fell short",
    "unreliable", "misfire", "misread", "misreads", "wrong", "cannot", "can not", "does not",
    "not reliable", "less reliable", "defect", "temper expectations", "under the claim",
    "hot spots", "loud", "throttle", "lag", "stutter", "drop", "dropout",
)

HEDGE_MARKERS: tuple[str, ...] = (
    "might", "maybe", "perhaps", "seems", "appears", "in our experience", "for me",
    "anecdotally", "i think", "probably",
)

FIRST_PERSON_MARKERS: tuple[str, ...] = (
    " i ", " i've", " i have", " my ", " we ", " our ", " mine ", "for me",
)

MEASUREMENT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:hours?|hrs?|minutes?|mins?|decibels?|db|grams?|g\b|newtons?|"
    r"hz|khz|kilometres?|kilometers?|km/h|percent|%|nits|watts?|degrees?)\b"
)

SPEC_MARKERS: tuple[str, ...] = (
    "specification", "specifications", "spec:", "driver unit", "frequency response",
    "bluetooth version", "codec", "charging time", "weight:", "supports", "up to",
)

COMPARISON_MARKERS: tuple[str, ...] = (
    "compared with", "compared to", "versus", " vs ", "previous generation", "than the",
    "better than", "worse than",
)

# Context qualifiers: these are what turn a naive contradiction into an honest,
# explainable, context-dependent conflict.
CONTEXT_QUALIFIERS: dict[str, tuple[str, ...]] = {
    "indoors / quiet environment": (
        "indoor", "indoors", "quiet room", "quiet studio", "home office", "office",
        "from a quiet", "meetings", "studio",
    ),
    "outdoors / wind": (
        "outdoor", "outdoors", "outside", "wind", "windy", "breeze", "walking to",
        "wind tunnel", "platform",
    ),
    "cold weather / gloves": ("cold", "winter", "gloves", "cold fingers"),
    "air travel": ("plane", "flight", "aircraft", "flying", "flew"),
    "commuting / transit": ("commute", "commuting", "train", "subway", "underground"),
    "with LDAC enabled": ("ldac",),
}


STOPWORDS: frozenset[str] = frozenset(
    (
        "a an and are as at be been but by can come could did do does doing for from had has "
        "have how i if in is it its me my of on or our so than that the their them then there "
        "these they this to was we were what when where which who why will with would you your"
    ).split()
)


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def content_words(text: str) -> set[str]:
    """Words that actually carry meaning, for relevance scoring."""

    return {token for token in words(text) if len(token) > 2 and token not in STOPWORDS}


def normalise(text: str) -> str:
    return " ".join(words(text))


def sentences(text: str) -> list[str]:
    parts: list[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        for sentence in _SENTENCE_RE.split(block):
            sentence = sentence.strip()
            if sentence:
                parts.append(sentence)
    return parts


def stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def count_markers(text: str, markers: tuple[str, ...]) -> int:
    padded = f" {text.lower()} "
    return sum(1 for marker in markers if marker in padded)


def topic_for(text: str, dimensions: list[Dimension]) -> tuple[str | None, int]:
    """Route a piece of text to the best-matching research dimension."""

    padded = f" {text.lower()} "
    best_name: str | None = None
    best_score = 0
    best_position = len(padded) + 1
    for dimension in dimensions:
        score = 0
        earliest = len(padded) + 1
        for keyword in dimension.keywords:
            position = padded.find(keyword)
            if position == -1:
                continue
            score += len(keyword.split())
            earliest = min(earliest, position)
            if position <= LEAD_WINDOW:
                # A sentence is usually about whatever it opens with: "Battery, I
                # got about 28 hours with noise cancelling on" is about battery.
                score += 2
        if score > best_score or (score == best_score and score > 0 and earliest < best_position):
            best_name, best_score, best_position = dimension.name, score, earliest
    return best_name, best_score


def _is_negated(padded: str, start: int, end: int) -> bool:
    before = padded[max(0, start - 22) : start]
    after = padded[end : end + 26]
    if any(negator in before for negator in PRE_NEGATORS):
        return True
    return any(negator in after for negator in POST_NEGATORS)


def polarity_counts(text: str) -> tuple[int, int]:
    """Count polarity markers, flipping any that sit inside a negation.

    "no complaints", "no creaking at all" and "defects were rare" are positive
    statements that a naive keyword count reads as negative.
    """

    padded = f" {text.lower()} "
    positive = 0
    negative = 0

    for marker in POSITIVE_MARKERS:
        start = padded.find(marker)
        while start != -1:
            end = start + len(marker)
            if _is_negated(padded, start, end):
                negative += 1
            else:
                positive += 1
            start = padded.find(marker, end)

    for marker in NEGATIVE_MARKERS:
        start = padded.find(marker)
        while start != -1:
            end = start + len(marker)
            if _is_negated(padded, start, end):
                positive += 1
            else:
                negative += 1
            start = padded.find(marker, end)

    return positive, negative


def sentiment_for(text: str) -> Sentiment:
    positive, negative = polarity_counts(text)
    if positive and negative:
        # A single sentence that swings both ways is genuinely mixed; a clear
        # majority still resolves.
        if positive >= negative * 2:
            return Sentiment.POSITIVE
        if negative >= positive * 2:
            return Sentiment.NEGATIVE
        return Sentiment.MIXED
    if positive:
        return Sentiment.POSITIVE
    if negative:
        return Sentiment.NEGATIVE
    return Sentiment.NEUTRAL


def evidence_type_for(text: str, source_type: SourceType, channel: Channel) -> EvidenceType:
    lowered = f" {text.lower()} "
    if count_markers(lowered, SPEC_MARKERS) and source_type == SourceType.OFFICIAL_DOC:
        return EvidenceType.SPECIFICATION
    if MEASUREMENT_RE.search(lowered):
        return EvidenceType.MEASUREMENT
    if count_markers(lowered, COMPARISON_MARKERS):
        return EvidenceType.COMPARISON
    if source_type == SourceType.OFFICIAL_DOC:
        return EvidenceType.CLAIM
    if channel in (Channel.REDDIT,) or source_type in (
        SourceType.FORUM_POST,
        SourceType.USER_EXPERIENCE,
    ):
        if count_markers(lowered, FIRST_PERSON_MARKERS):
            return EvidenceType.CUSTOMER_EXPERIENCE
        return EvidenceType.ANECDOTE
    if source_type in (SourceType.PROFESSIONAL_REVIEW, SourceType.VIDEO_REVIEW):
        return EvidenceType.EXPERT_OPINION
    return EvidenceType.FACT


def strength_for(
    text: str, source_type: SourceType, evidence_type: EvidenceType, authority: float
) -> Strength:
    if evidence_type in (EvidenceType.MEASUREMENT, EvidenceType.SPECIFICATION) and authority >= 0.6:
        return Strength.STRONG
    if evidence_type == EvidenceType.ANECDOTE:
        return Strength.WEAK
    if count_markers(text, HEDGE_MARKERS):
        return Strength.WEAK
    if source_type == SourceType.OFFICIAL_DOC:
        # Manufacturer marketing about its own product is never strong evidence.
        return Strength.WEAK
    if authority >= 0.7 and evidence_type in (
        EvidenceType.EXPERT_OPINION,
        EvidenceType.FACT,
        EvidenceType.COMPARISON,
    ):
        return Strength.MODERATE
    if evidence_type == EvidenceType.CUSTOMER_EXPERIENCE:
        return Strength.MODERATE
    return Strength.MODERATE


def context_qualifiers(text: str) -> list[str]:
    padded = f" {text.lower()} "
    found: list[str] = []
    for label, markers in CONTEXT_QUALIFIERS.items():
        if any(marker in padded for marker in markers):
            found.append(label)
    return found


def dominant_qualifiers(texts: list[str]) -> str:
    """The context labels that best characterise a set of reports.

    Used to explain *why* two groups of sources disagree instead of picking a
    winner between them.
    """

    counts: dict[str, int] = {}
    for text in texts:
        for qualifier in context_qualifiers(text):
            counts[qualifier] = counts.get(qualifier, 0) + 1
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return " and ".join(name for name, _ in ordered[:2])


def shingles(text: str, size: int = 5) -> set[str]:
    tokens = words(text)
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    return intersection / union if union else 0.0


def grounded_in(candidate: str, source_text: str, threshold: float = 0.6) -> bool:
    """True when ``candidate`` is really drawn from ``source_text``.

    Used to reject LLM output that quotes text no source ever contained.
    """

    candidate_tokens = set(words(candidate))
    if not candidate_tokens:
        return False
    source_tokens = set(words(source_text))
    overlap = len(candidate_tokens & source_tokens) / len(candidate_tokens)
    return overlap >= threshold


def estimate_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 characters per token)."""

    return max(1, (len(text) + 3) // 4)


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()
