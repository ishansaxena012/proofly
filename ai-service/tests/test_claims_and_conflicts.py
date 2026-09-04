"""Claim generation and conflict preservation."""

from __future__ import annotations

from app.graph.nodes.claim_generation import claim_generation_node
from app.graph.schemas import ClaimGenerationResult, GeneratedClaim
from app.models.enums import ClaimStatus, EventType, Relationship, Sentiment
from app.services.conflict import is_genuine_conflict
from tests.factories import build_analysis_state


def test_conflict_definition_ignores_a_lone_weak_outlier():
    assert is_genuine_conflict({"g1", "g2", "g3"}, {"g4", "g5"}) is True
    assert is_genuine_conflict({"g1", "g2", "g3"}, {"g4"}) is False
    # ...unless the lone voice is a strong measurement.
    assert is_genuine_conflict({"g1", "g2"}, {"g4"}, negative_has_strong=True) is True
    assert is_genuine_conflict({"g1"}, set()) is False


async def test_claims_link_evidence_with_explicit_relationships(job_context):
    state = build_analysis_state(job_context.job_id)
    result = await claim_generation_node(job_context, state)
    claims = result["claims"]
    evidence_ids = {item.id for item in state["evidence"]}

    assert claims
    for claim in claims:
        assert claim.links
        for link in claim.links:
            assert link.evidence_id in evidence_ids
            assert link.relationship in set(Relationship)


async def test_a_genuine_disagreement_survives_as_a_conflict(job_context):
    state = build_analysis_state(job_context.job_id)
    result = await claim_generation_node(job_context, state)

    conflicts = result["conflicts"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.topic == "Microphone & Call Quality"
    assert conflict.resolved is False
    assert conflict.position_a.evidence_ids and conflict.position_b.evidence_ids
    assert set(conflict.position_a.evidence_ids) & set(conflict.position_b.evidence_ids) == set()
    # The explanation names the condition that separates the two sides.
    assert "indoors" in conflict.explanation.lower()
    assert "outdoors" in conflict.explanation.lower() or "wind" in conflict.explanation.lower()


async def test_the_conflicted_claim_keeps_both_sides(job_context):
    state = build_analysis_state(job_context.job_id)
    result = await claim_generation_node(job_context, state)
    claim = next(c for c in result["claims"] if c.topic == "Microphone & Call Quality")

    assert claim.status == ClaimStatus.CONTESTED
    assert claim.evidence_ids(Relationship.SUPPORTS)
    assert claim.evidence_ids(Relationship.CONTRADICTS)


async def test_an_isolated_outlier_is_not_promoted_to_a_conflict(job_context):
    state = build_analysis_state(job_context.job_id)
    result = await claim_generation_node(job_context, state)
    topics = {conflict.topic for conflict in result["conflicts"]}
    # Battery Life has many positives and exactly one dissenting report.
    assert "Battery Life" not in topics
    battery = next(c for c in result["claims"] if c.topic == "Battery Life")
    # ...but the dissent is still recorded rather than dropped.
    assert battery.evidence_ids(Relationship.CONTRADICTS)


async def test_claims_citing_unknown_evidence_are_rejected(job_context, monkeypatch):
    state = build_analysis_state(job_context.job_id)

    async def fabricate(prompt, schema, *, task="", context=None):
        if task != "claim_generation":
            return await original(prompt, schema, task=task, context=context)
        return ClaimGenerationResult(
            claims=[
                GeneratedClaim(
                    topic=context["topic"],
                    statement="Everything is perfect.",
                    supporting_evidence_ids=["evidence-that-does-not-exist"],
                )
            ]
        )

    original = job_context.llm.generate_structured
    monkeypatch.setattr(job_context.llm, "generate_structured", fabricate)
    result = await claim_generation_node(job_context, state)
    assert result["claims"] == []


async def test_claims_with_numbers_absent_from_evidence_are_rejected(job_context, monkeypatch):
    state = build_analysis_state(job_context.job_id)
    original = job_context.llm.generate_structured

    async def fabricate(prompt, schema, *, task="", context=None):
        if task != "claim_generation":
            return await original(prompt, schema, task=task, context=context)
        ids = [item["id"] for item in context["evidence"]]
        return ClaimGenerationResult(
            claims=[
                GeneratedClaim(
                    topic=context["topic"],
                    statement="Battery life is exactly 9999 hours in every situation.",
                    supporting_evidence_ids=ids,
                )
            ]
        )

    monkeypatch.setattr(job_context.llm, "generate_structured", fabricate)
    result = await claim_generation_node(job_context, state)
    assert result["claims"] == []


async def test_claims_generated_event_reports_conflicts(job_context, backend_calls):
    state = build_analysis_state(job_context.job_id)
    await claim_generation_node(job_context, state)
    event = next(
        c["json"]
        for c in backend_calls
        if c["path"].endswith("/events") and c["json"]["eventType"] == EventType.CLAIMS_GENERATED.value
    )
    assert event["payload"]["conflictCount"] == 1
    assert event["payload"]["conflictTopics"] == ["Microphone & Call Quality"]


async def test_claims_are_pushed_to_the_backend_with_their_relationships(job_context, backend_calls):
    state = build_analysis_state(job_context.job_id)
    await claim_generation_node(job_context, state)
    payload = next(c["json"] for c in backend_calls if c["path"].endswith("/claims"))
    assert payload["claims"]
    assert payload["claimEvidence"]
    assert {row["relationship"] for row in payload["claimEvidence"]} <= {
        relationship.value for relationship in Relationship
    }


def test_fixture_state_contains_both_sides_of_the_microphone_split(job_context):
    state = build_analysis_state(job_context.job_id)
    mic = [item for item in state["evidence"] if item.topic == "Microphone & Call Quality"]
    assert any(item.sentiment == Sentiment.POSITIVE for item in mic)
    assert any(item.sentiment == Sentiment.NEGATIVE for item in mic)
