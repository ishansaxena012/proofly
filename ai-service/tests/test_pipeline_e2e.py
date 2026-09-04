"""End-to-end golden path: the full graph over the Sony WH-1000XM6 fixture."""

from __future__ import annotations

from app.fixtures import all_fixture_urls
from app.models.enums import ClaimStatus, EventType, JobStatus, SourceStatus


async def test_golden_path_produces_a_complete_report(golden_run, backend_calls):
    state = golden_run

    assert state["terminal_status"] == JobStatus.COMPLETED.value
    report = state["report"]
    assert report is not None
    assert report.demo_mode is True
    assert 0 <= report.overall_score <= 100
    assert 0.0 <= report.confidence <= 1.0
    assert report.verdict
    assert report.executive_summary

    # Sources, evidence and claims all made it through.
    fetched = [s for s in state["sources"] if s.status == SourceStatus.FETCHED]
    assert len(fetched) >= 8
    assert len(state["evidence"]) >= 25
    assert len(state["claims"]) >= 5

    # Every channel contributed.
    outcomes = state["channel_outcomes"]
    assert {"WEB", "REDDIT", "YOUTUBE"} <= set(outcomes)
    assert all(outcome["status"] == "OK" for outcome in outcomes.values())


async def test_golden_path_emits_the_contract_events(backend_calls, golden_run):
    events = [
        call["json"]["eventType"]
        for call in backend_calls
        if call["path"].endswith("/events")
    ]
    for required in (
        EventType.PRODUCT_IDENTIFIED,
        EventType.RESEARCH_STARTED,
        EventType.WEB_RESEARCH_COMPLETED,
        EventType.REDDIT_RESEARCH_COMPLETED,
        EventType.YOUTUBE_RESEARCH_COMPLETED,
        EventType.EVIDENCE_EXTRACTION_STARTED,
        EventType.EVIDENCE_EXTRACTION_COMPLETED,
        EventType.CLAIMS_GENERATED,
        EventType.VERIFICATION_STARTED,
        EventType.VERIFICATION_COMPLETED,
        EventType.REPORT_GENERATION_STARTED,
        EventType.REPORT_COMPLETED,
    ):
        assert required.value in events, f"missing event {required.value}"


async def test_backend_callbacks_use_the_contract_paths(backend_calls, golden_run, job_context):
    paths = {call["path"] for call in backend_calls}
    job_id = job_context.job_id
    for suffix in ("status", "product", "events", "sources", "evidence", "claims", "report"):
        assert f"/internal/v1/research/{job_id}/{suffix}" in paths

    assert all(call["key"] == "test-internal-key" for call in backend_calls)

    statuses = [
        call["json"]["status"] for call in backend_calls if call["path"].endswith("/status")
    ]
    assert JobStatus.IDENTIFYING_PRODUCT.value in statuses
    assert JobStatus.PLANNING_RESEARCH.value in statuses
    assert JobStatus.RESEARCHING.value in statuses
    assert JobStatus.EXTRACTING_EVIDENCE.value in statuses
    assert JobStatus.ANALYZING.value in statuses
    assert JobStatus.VERIFYING.value in statuses
    assert JobStatus.GENERATING_REPORT.value in statuses
    assert statuses[-1] == JobStatus.COMPLETED.value


async def test_report_dto_matches_the_api_contract_shape(golden_run):
    payload = golden_run["report"].to_wire()
    expected_keys = {
        "researchJobId", "demoMode", "overallScore", "verdict", "confidence",
        "executiveSummary", "categoryScores", "keyStrengths", "keyWeaknesses",
        "keyFindings", "commonPraise", "commonComplaints", "conflicts",
        "longTermOwnership", "whoShouldBuy", "whoShouldAvoid", "caveats", "sources", "claims",
    }
    assert expected_keys == set(payload)

    category = payload["categoryScores"][0]
    assert set(category) == {"category", "score", "confidence"}

    claim = payload["claims"][0]
    assert set(claim) == {
        "id", "topic", "statement", "status", "confidence",
        "supportingEvidence", "contradictingEvidence",
    }

    conflict = payload["conflicts"][0]
    assert set(conflict) == {"topic", "positionA", "positionB", "explanation", "resolved"}
    assert set(conflict["positionA"]) == {"text", "evidenceIds"}


async def test_no_source_url_is_invented(golden_run):
    allowed = all_fixture_urls()
    for source in golden_run["report"].sources:
        assert source.url in allowed


async def test_demo_mode_is_disclosed_in_the_report(golden_run):
    report = golden_run["report"]
    assert any("DEMO MODE" in caveat for caveat in report.caveats)
    assert "demo" in report.executive_summary.lower()


async def test_every_claim_is_traceable_to_evidence(golden_run):
    report = golden_run["report"]
    evidence_ids = {item.id for item in golden_run["evidence"]}
    for claim in report.claims:
        cited = claim.supporting_evidence + claim.contradicting_evidence
        if claim.status != ClaimStatus.INSUFFICIENT_EVIDENCE.value:
            assert cited, f"claim {claim.id} has no evidence"
        for reference in cited:
            assert reference.id in evidence_ids
