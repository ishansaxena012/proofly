"""Verification: unsupported and overstated claims must be downgraded or removed."""

from __future__ import annotations

from app.graph.nodes.claim_generation import claim_generation_node
from app.graph.nodes.verification import verification_node
from app.models.domain import Claim, ClaimEvidenceLink
from app.models.enums import ClaimStatus, EventType, Relationship
from tests.factories import build_analysis_state


async def _generated(job_context) -> dict:
    state = build_analysis_state(job_context.job_id)
    state.update(await claim_generation_node(job_context, state))
    return state


async def test_a_single_weak_anecdote_is_downgraded_to_insufficient_evidence(job_context):
    state = await _generated(job_context)
    before = next(c for c in state["claims"] if c.topic == "Build Quality")
    assert before.status != ClaimStatus.INSUFFICIENT_EVIDENCE

    state.update(await verification_node(job_context, state))
    after = next(c for c in state["claims"] if c.topic == "Build Quality")

    assert after.status == ClaimStatus.INSUFFICIENT_EVIDENCE
    assert after.confidence <= 0.25
    assert any("anecdot" in note.lower() for note in after.verification_notes)
    # The evidence link is kept, so the reader can still see what was said.
    assert after.links


async def test_unanimous_independent_evidence_stays_supported(job_context):
    state = await _generated(job_context)
    state.update(await verification_node(job_context, state))
    claim = next(c for c in state["claims"] if c.topic == "Sound Quality")
    assert claim.status == ClaimStatus.SUPPORTED
    assert claim.confidence > 0.5


async def test_a_contested_claim_is_not_resolved_by_majority(job_context):
    state = await _generated(job_context)
    state.update(await verification_node(job_context, state))
    claim = next(c for c in state["claims"] if c.topic == "Microphone & Call Quality")
    assert claim.status == ClaimStatus.CONTESTED
    assert claim.evidence_ids(Relationship.SUPPORTS)
    assert claim.evidence_ids(Relationship.CONTRADICTS)
    assert claim.confidence <= 0.5


async def test_a_claim_with_no_valid_evidence_is_removed(job_context):
    state = await _generated(job_context)
    state["claims"] = state["claims"] + [
        Claim(
            id="ghost-claim",
            research_job_id=job_context.job_id,
            topic="Sound Quality",
            statement="The headphones are objectively perfect for everyone.",
            status=ClaimStatus.SUPPORTED,
            confidence=0.99,
            links=[
                ClaimEvidenceLink(evidence_id="no-such-evidence", relationship=Relationship.SUPPORTS)
            ],
        )
    ]
    state.update(await verification_node(job_context, state))
    assert all(claim.id != "ghost-claim" for claim in state["claims"])
    assert any("removed during verification" in limit for limit in state["limitations"])


async def test_evidence_about_another_topic_is_dropped(job_context):
    state = await _generated(job_context)
    claim = next(c for c in state["claims"] if c.topic == "Sound Quality")
    claim.links = claim.links + [
        ClaimEvidenceLink(evidence_id="evidence-7", relationship=Relationship.SUPPORTS)  # Battery Life
    ]
    state.update(await verification_node(job_context, state))
    verified = next(c for c in state["claims"] if c.topic == "Sound Quality")
    assert "evidence-7" not in verified.evidence_ids()
    assert any("not 'Sound Quality'" in note for note in verified.verification_notes)


async def test_overstated_wording_flagged_by_the_model_downgrades_the_claim(job_context, monkeypatch):
    state = await _generated(job_context)
    claim = next(c for c in state["claims"] if c.topic == "Sound Quality")
    claim.statement = "Sound quality is always perfect for every user, universally."

    state.update(await verification_node(job_context, state))
    verified = next(c for c in state["claims"] if c.topic == "Sound Quality")
    assert verified.status != ClaimStatus.SUPPORTED
    assert any("Absolute wording" in note for note in verified.verification_notes)


async def test_numbers_absent_from_the_evidence_downgrade_the_claim(job_context):
    state = await _generated(job_context)
    claim = next(c for c in state["claims"] if c.topic == "Sound Quality")
    claim.statement = "Sound quality measured 42 points above every rival."

    state.update(await verification_node(job_context, state))
    verified = next(c for c in state["claims"] if c.topic == "Sound Quality")
    assert verified.status != ClaimStatus.SUPPORTED
    assert any("42" in note for note in verified.verification_notes)


async def test_statuses_short_of_supported_get_cautious_wording(job_context):
    state = await _generated(job_context)
    state.update(await verification_node(job_context, state))
    for claim in state["claims"]:
        if claim.status == ClaimStatus.INSUFFICIENT_EVIDENCE:
            assert claim.statement.startswith("Insufficient evidence:")
        elif claim.status == ClaimStatus.CONTESTED:
            assert claim.statement.startswith("Contested:")
        elif claim.status == ClaimStatus.PARTIALLY_SUPPORTED:
            assert claim.statement.startswith("Partially supported:")


async def test_verification_events_report_the_status_breakdown(job_context, backend_calls):
    state = await _generated(job_context)
    await verification_node(job_context, state)
    event = next(
        c["json"]
        for c in backend_calls
        if c["path"].endswith("/events")
        and c["json"]["eventType"] == EventType.VERIFICATION_COMPLETED.value
    )
    breakdown = event["payload"]["statusBreakdown"]
    assert set(breakdown) == {status.value for status in ClaimStatus}
    assert sum(breakdown.values()) == event["payload"]["claimCount"]
