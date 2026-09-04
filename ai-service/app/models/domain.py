"""Domain models for the research pipeline.

Wire-facing models inherit from :class:`CamelModel` so ``model_dump(by_alias=True)``
produces exactly the camelCase JSON shapes fixed in ``docs/API.md`` while the Python
code keeps snake_case attributes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import (
    Channel,
    ClaimStatus,
    EvidenceType,
    Relationship,
    SectionType,
    Sentiment,
    SourceStatus,
    SourceType,
    Strength,
)


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=False,
        ser_json_timedelta="iso8601",
    )


# ───────────────────────────── product resolution ──────────────────────────


class ProductResolution(CamelModel):
    """Output of the product resolver node."""

    raw_query: str
    canonical_name: str | None = None
    brand: str | None = None
    category: str | None = None
    model: str | None = None
    resolution_confidence: float = 0.0
    ambiguous: bool = False
    ambiguity_reason: str | None = None
    clarification_options: list[str] = Field(default_factory=list)


# ───────────────────────────── research planning ───────────────────────────


class ResearchDimension(CamelModel):
    name: str
    rationale: str
    universal: bool = False
    queries: list[str] = Field(default_factory=list)


class ResearchPlan(CamelModel):
    category: str
    category_matched: bool
    dimensions: list[ResearchDimension] = Field(default_factory=list)
    web_queries: list[str] = Field(default_factory=list)
    reddit_queries: list[str] = Field(default_factory=list)
    youtube_queries: list[str] = Field(default_factory=list)


# ───────────────────────────── sources / documents ─────────────────────────


class Source(CamelModel):
    id: str = Field(default_factory=new_id)
    channel: Channel
    url: str
    title: str | None = None
    source_type: SourceType = SourceType.GENERIC
    authority_score: float = 0.5
    first_hand: bool = False
    independence_group_id: str | None = None
    status: SourceStatus = SourceStatus.FETCHED
    failure_reason: str | None = None
    published_at: date | None = None
    fetched_at: datetime = Field(default_factory=utcnow)
    # internal-only, never persisted by the backend (no endpoint for documents)
    raw_text: str = ""
    is_demo_fixture: bool = False

    def to_wire(self) -> dict:
        return {
            "id": self.id,
            "channel": self.channel.value,
            "url": self.url,
            "title": self.title,
            "sourceType": self.source_type.value,
            "authorityScore": round(self.authority_score, 4),
            "firstHand": self.first_hand,
            "independenceGroupId": self.independence_group_id,
            "status": self.status.value,
            "failureReason": self.failure_reason,
            "fetchedAt": self.fetched_at.isoformat(),
        }


class Document(CamelModel):
    id: str = Field(default_factory=new_id)
    source_id: str
    raw_text: str
    content_hash: str
    token_count: int


class Passage(CamelModel):
    id: str = Field(default_factory=new_id)
    document_id: str
    source_id: str
    text: str
    position: int
    embedding: list[float] | None = None


# ───────────────────────────── evidence / claims ───────────────────────────


class Evidence(CamelModel):
    id: str = Field(default_factory=new_id)
    research_job_id: str
    source_id: str
    passage_id: str | None = None
    topic: str
    sentiment: Sentiment = Sentiment.NEUTRAL
    evidence_type: EvidenceType = EvidenceType.CLAIM
    strength: Strength = Strength.MODERATE
    text: str

    def to_wire(self) -> dict:
        return {
            "id": self.id,
            "sourceId": self.source_id,
            # documents/passages have no internal persistence endpoint, so the
            # backend column stays null; traceability runs evidence -> source -> url.
            "passageId": None,
            "topic": self.topic,
            "sentiment": self.sentiment.value,
            "evidenceType": self.evidence_type.value,
            "strength": self.strength.value,
            "text": self.text,
        }


class ClaimEvidenceLink(CamelModel):
    evidence_id: str
    relationship: Relationship


class Claim(CamelModel):
    id: str = Field(default_factory=new_id)
    research_job_id: str
    topic: str
    statement: str
    status: ClaimStatus = ClaimStatus.INSUFFICIENT_EVIDENCE
    confidence: float = 0.0
    links: list[ClaimEvidenceLink] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)

    def evidence_ids(self, relationship: Relationship | None = None) -> list[str]:
        return [
            link.evidence_id
            for link in self.links
            if relationship is None or link.relationship == relationship
        ]

    def to_wire(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "statement": self.statement,
            "status": self.status.value,
            "confidence": round(self.confidence, 4),
            "verificationNotes": list(self.verification_notes),
        }


# ───────────────────────────── report DTO (docs/API.md) ────────────────────


class EvidenceBackedText(CamelModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class FindingRef(CamelModel):
    text: str
    claim_id: str


class CategoryScore(CamelModel):
    category: str
    score: int
    confidence: float


class ConflictPosition(CamelModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class Conflict(CamelModel):
    topic: str
    position_a: ConflictPosition
    position_b: ConflictPosition
    explanation: str
    resolved: bool = False


class ReportSourceRef(CamelModel):
    id: str
    url: str
    title: str | None = None
    source_type: str
    channel: str


class ReportEvidenceRef(CamelModel):
    id: str
    text: str
    source_id: str


class ReportClaim(CamelModel):
    id: str
    topic: str
    statement: str
    status: str
    confidence: float
    supporting_evidence: list[ReportEvidenceRef] = Field(default_factory=list)
    contradicting_evidence: list[ReportEvidenceRef] = Field(default_factory=list)


class Report(CamelModel):
    research_job_id: str
    demo_mode: bool
    overall_score: int
    verdict: str
    confidence: float
    executive_summary: str
    category_scores: list[CategoryScore] = Field(default_factory=list)
    key_strengths: list[EvidenceBackedText] = Field(default_factory=list)
    key_weaknesses: list[EvidenceBackedText] = Field(default_factory=list)
    key_findings: list[FindingRef] = Field(default_factory=list)
    common_praise: list[EvidenceBackedText] = Field(default_factory=list)
    common_complaints: list[EvidenceBackedText] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    long_term_ownership: EvidenceBackedText | None = None
    who_should_buy: list[str] = Field(default_factory=list)
    who_should_avoid: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sources: list[ReportSourceRef] = Field(default_factory=list)
    claims: list[ReportClaim] = Field(default_factory=list)

    def to_wire(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")


class ReportSection(CamelModel):
    section_type: SectionType
    title: str
    content: dict
    order_index: int
