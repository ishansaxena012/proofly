"""Report synthesis: derived numbers, preserved conflicts, disclosed limitations."""

from __future__ import annotations

from datetime import date

from app.graph.nodes.claim_generation import claim_generation_node
from app.graph.nodes.report_synthesis import report_synthesis_node
from app.graph.nodes.verification import verification_node
from app.graph.schemas import NarrativeSummary
from app.models.enums import EventType, JobStatus, SectionType, Sentiment, SourceStatus
from app.services import scoring
from tests.factories import build_analysis_state, build_evidence, build_sources


async def _analysed(job_context) -> dict:
    state = build_analysis_state(job_context.job_id)
    state.update(await claim_generation_node(job_context, state))
    state.update(await verification_node(job_context, state))
    return state


# ── deterministic scoring ──────────────────────────────────────────────────


def test_scores_are_derived_from_evidence_not_invented():
    sources = {source.id: source for source in build_sources()}
    evidence = build_evidence("job")
    scores = {item.topic: item for item in scoring.score_topics(evidence, sources)}

    assert scores["Sound Quality"].score > scores["Microphone & Call Quality"].score
    assert scores["Build Quality"].score < 50
    assert all(0 <= item.score <= 100 for item in scores.values())
    assert all(0.0 <= item.confidence <= 1.0 for item in scores.values())


def test_duplicate_sources_cannot_inflate_a_score():
    sources = {source.id: source for source in build_sources()}
    evidence = build_evidence("job")
    baseline = scoring.score_topic(
        "Sound Quality", [e for e in evidence if e.topic == "Sound Quality"], sources
    )

    # Source 6 is a syndicated copy of source 1 — same independence group — so
    # repeating source 1's praise through it must not raise the score.
    duplicate = next(e for e in evidence if e.topic == "Sound Quality").model_copy(
        update={"id": "evidence-dup", "source_id": "source-6"}
    )
    inflated = scoring.score_topic(
        "Sound Quality",
        [e for e in evidence if e.topic == "Sound Quality"] + [duplicate],
        sources,
    )
    assert inflated.score == baseline.score
    assert inflated.group_count == baseline.group_count


def test_confidence_rises_with_independent_agreement():
    sources = {source.id: source for source in build_sources()}
    evidence = build_evidence("job")
    single_group = [e for e in evidence if e.topic == "Build Quality"]
    many_groups = [e for e in evidence if e.topic == "Sound Quality"]
    assert (
        scoring.score_topic("Sound Quality", many_groups, sources).confidence
        > scoring.score_topic("Build Quality", single_group, sources).confidence
    )


def test_stale_evidence_lowers_confidence():
    sources = {source.id: source for source in build_sources()}
    evidence = [e for e in build_evidence("job") if e.topic == "Sound Quality"]
    fresh = scoring.score_topic("Sound Quality", evidence, sources, today=date(2025, 9, 1))
    stale = scoring.score_topic("Sound Quality", evidence, sources, today=date(2032, 9, 1))
    assert stale.confidence < fresh.confidence


def test_overall_score_uses_neutral_equal_weights():
    class Fake:
        def __init__(self, score, confidence):
            self.score = score
            self.confidence = confidence

    assert scoring.overall_score([Fake(80, 0.9), Fake(40, 0.9)]) == 60
    assert scoring.overall_score([]) == 0


def test_verdicts_follow_score_and_confidence():
    assert scoring.verdict_for(90, 0.8, True) == "Recommended"
    assert scoring.verdict_for(70, 0.8, True) == "Recommended with caveats"
    assert scoring.verdict_for(55, 0.8, True).startswith("Mixed")
    assert scoring.verdict_for(20, 0.8, True) == "Not recommended"
    assert "Insufficient" in scoring.verdict_for(90, 0.1, True)
    assert "Insufficient" in scoring.verdict_for(90, 0.9, False)


# ── the node ───────────────────────────────────────────────────────────────


async def test_report_assembles_the_full_dto(job_context):
    state = await _analysed(job_context)
    result = await report_synthesis_node(job_context, state)
    report = result["report"]

    assert result["terminal_status"] == JobStatus.COMPLETED.value
    assert report.research_job_id == job_context.job_id
    assert report.category_scores
    assert report.key_findings
    assert report.claims
    assert report.sources
    assert report.who_should_buy and report.who_should_avoid
    assert report.long_term_ownership is not None

    computed = scoring.overall_score(
        scoring.score_topics(state["evidence"], {s.id: s for s in state["sources"]})
    )
    assert report.overall_score == computed


async def test_the_conflict_reaches_the_report(job_context):
    state = await _analysed(job_context)
    report = (await report_synthesis_node(job_context, state))["report"]
    assert [conflict.topic for conflict in report.conflicts] == ["Microphone & Call Quality"]
    assert report.conflicts[0].resolved is False
    assert report.conflicts[0].position_a.evidence_ids
    assert report.conflicts[0].position_b.evidence_ids


async def test_common_praise_requires_more_than_one_independent_group(job_context):
    state = await _analysed(job_context)
    report = (await report_synthesis_node(job_context, state))["report"]
    single_group_topics = {"Build Quality"}
    assert not (
        {item.text.split(" is ")[0] for item in report.common_complaints} & single_group_topics
    )


async def test_all_sections_are_emitted_in_order(job_context):
    state = await _analysed(job_context)
    sections = (await report_synthesis_node(job_context, state))["sections"]
    assert [section.section_type for section in sections] == list(SectionType)
    assert [section.order_index for section in sections] == list(range(len(sections)))
    assert all(isinstance(section.content, dict) for section in sections)


async def test_a_generated_summary_with_invented_numbers_is_discarded(job_context, monkeypatch):
    state = await _analysed(job_context)
    original = job_context.llm.generate_structured

    async def hallucinate(prompt, schema, *, task="", context=None):
        if task == "narrative":
            return NarrativeSummary(
                executive_summary="These headphones scored 987 points in 55 independent labs."
            )
        return await original(prompt, schema, task=task, context=context)

    monkeypatch.setattr(job_context.llm, "generate_structured", hallucinate)
    report = (await report_synthesis_node(job_context, state))["report"]
    assert "987" not in report.executive_summary
    assert str(report.overall_score) in report.executive_summary


async def test_a_failed_channel_degrades_but_does_not_fail_the_job(job_context, backend_calls):
    state = await _analysed(job_context)
    state["channel_outcomes"]["YOUTUBE"] = {
        "status": "FAILED",
        "sources": 0,
        "error": "provider unavailable",
    }
    result = await report_synthesis_node(job_context, state)

    assert result["terminal_status"] == JobStatus.PARTIALLY_COMPLETED.value
    assert any("YOUTUBE research was unavailable" in c for c in result["report"].caveats)
    events = [c["json"]["eventType"] for c in backend_calls if c["path"].endswith("/events")]
    assert EventType.JOB_PARTIALLY_COMPLETED.value in events


async def test_no_retrievable_sources_fails_with_insufficient_data(job_context, backend_calls):
    state = await _analysed(job_context)
    for source in state["sources"]:
        source.status = SourceStatus.FAILED
    result = await report_synthesis_node(job_context, state)

    assert result["report"] is None
    assert result["terminal_status"] == JobStatus.FAILED.value
    assert result["error_code"] == "INSUFFICIENT_DATA"


async def test_report_is_pushed_with_its_sections(job_context, backend_calls):
    state = await _analysed(job_context)
    await report_synthesis_node(job_context, state)
    payload = next(c["json"] for c in backend_calls if c["path"].endswith("/report"))
    assert payload["researchJobId"] == job_context.job_id
    assert payload["demoMode"] is True
    assert len(payload["sections"]) == len(SectionType)
    assert payload["sections"][0]["sectionType"] == SectionType.EXECUTIVE_SUMMARY.value


def test_evidence_fixture_has_both_polarities():
    evidence = build_evidence("job")
    assert any(item.sentiment == Sentiment.POSITIVE for item in evidence)
    assert any(item.sentiment == Sentiment.NEGATIVE for item in evidence)
