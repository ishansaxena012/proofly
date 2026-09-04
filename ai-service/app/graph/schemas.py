"""Pydantic schemas used for schema-constrained LLM generation.

These are the *only* shapes the pipeline will accept back from an LLM. Every
consumer additionally re-validates the content against the evidence store, so a
model that returns a well-formed but ungrounded answer still cannot get material
into a report.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductResolutionLLM(BaseModel):
    canonical_name: str = ""
    brand: str = ""
    category: str = ""
    model: str = ""
    ambiguous: bool = False
    ambiguity_reason: str = ""
    clarification_options: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class PlannedDimension(BaseModel):
    name: str
    rationale: str


class PlanExtension(BaseModel):
    dimensions: list[PlannedDimension] = Field(default_factory=list)


class ExtractedEvidence(BaseModel):
    passage_id: str
    topic: str
    evidence_type: str
    sentiment: str
    strength: str
    text: str


class EvidenceExtractionResult(BaseModel):
    items: list[ExtractedEvidence] = Field(default_factory=list)


class GeneratedClaim(BaseModel):
    topic: str
    statement: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    contextualizing_evidence_ids: list[str] = Field(default_factory=list)


class ClaimGenerationResult(BaseModel):
    claims: list[GeneratedClaim] = Field(default_factory=list)


class ConflictExplanation(BaseModel):
    explanation: str = ""
    resolved: bool = False


class VerificationVerdict(BaseModel):
    claim_id: str
    overstated: bool = False
    issues: list[str] = Field(default_factory=list)
    revised_statement: str = ""


class VerificationResult(BaseModel):
    verdicts: list[VerificationVerdict] = Field(default_factory=list)


class NarrativeSummary(BaseModel):
    executive_summary: str = ""
    who_should_buy: list[str] = Field(default_factory=list)
    who_should_avoid: list[str] = Field(default_factory=list)


class FollowupAnswer(BaseModel):
    answer: str = ""
    cited_evidence_ids: list[str] = Field(default_factory=list)
