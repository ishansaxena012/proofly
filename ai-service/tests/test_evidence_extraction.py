"""Evidence extraction: grounding, independence clustering, repeated patterns."""

from __future__ import annotations

from app.graph.nodes.evidence_extraction import evidence_extraction_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.research import (
    classify_web_source,
    publisher_key,
    reddit_research_node,
    web_research_node,
    youtube_research_node,
)
from app.graph.schemas import EvidenceExtractionResult, ExtractedEvidence
from app.graph.state import initial_state
from app.models.domain import ProductResolution, Source
from app.models.enums import Channel, EvidenceType, SourceStatus, SourceType
from app.services.chunking import build_document, split_passages
from app.services.heuristics import grounded_in
from app.services.independence import cluster_sources


async def _researched_state(job_context) -> dict:
    state = initial_state(job_context.job_id, "Sony WH-1000XM6", True)
    state["product"] = ProductResolution(
        raw_query="Sony WH-1000XM6",
        canonical_name="Sony WH-1000XM6",
        brand="Sony",
        model="WH-1000XM6",
        category="headphones",
        resolution_confidence=0.95,
    )
    state.update(await planner_node(job_context, state))
    for node in (web_research_node, reddit_research_node, youtube_research_node):
        result = await node(job_context, state)
        state["sources"] = state["sources"] + [
            s for s in result["sources"] if s.id not in {x.id for x in state["sources"]}
        ]
        state["documents"] = state["documents"] + result["documents"]
        state["passages"] = state["passages"] + result["passages"]
        state["channel_outcomes"] = {**state["channel_outcomes"], **result["channel_outcomes"]}
        state["limitations"] = state["limitations"] + result["limitations"]
    return state


# ── chunking ───────────────────────────────────────────────────────────────


def test_passages_are_paragraph_aligned_and_traceable():
    text = "\n".join(f"Paragraph number {i} with plenty of words to survive the filter." for i in range(6))
    document = build_document("source-1", text)
    passages = split_passages(document)
    assert passages
    assert all(passage.document_id == document.id for passage in passages)
    assert all(passage.source_id == "source-1" for passage in passages)
    assert [passage.position for passage in passages] == list(range(len(passages)))
    assert all(passage.text in text or passage.text.replace("\n", " ") in text.replace("\n", " ") for passage in passages)


# ── source classification ──────────────────────────────────────────────────


def test_publisher_key_uses_the_fixture_slug_not_the_shared_host():
    assert publisher_key("https://fixtures.proofly.invalid/web/sony-official/page") == "sony-official"
    assert publisher_key("https://www.example.com/sony/page") == "www.example.com"


def test_manufacturer_pages_are_never_first_hand():
    source_type, authority, first_hand = classify_web_source(
        "https://fixtures.proofly.invalid/web/sony-official/wh-1000xm6-product-page",
        "Sony WH-1000XM6 official",
        "Specifications. Driver unit: 12 mm dome type." * 10,
        "Sony",
    )
    assert source_type == SourceType.OFFICIAL_DOC
    assert first_hand is False
    assert authority < 0.7


def test_a_syndicated_copy_is_not_classified_as_the_manufacturer():
    source_type, _, _ = classify_web_source(
        "https://fixtures.proofly.invalid/web/gadgetwire-syndication/sony-announces-wh-1000xm6",
        "Sony announces the WH-1000XM6",
        "Sony has announced the WH-1000XM6. " * 20,
        "Sony",
    )
    assert source_type != SourceType.OFFICIAL_DOC


# ── independence clustering ────────────────────────────────────────────────


def test_syndicated_and_manufacturer_sources_share_an_independence_group():
    press_release = (
        "The headphones offer up to thirty hours of battery life with noise cancelling enabled, "
        "quick charging that provides three hours of playback from a three minute charge, and "
        "newly developed twelve millimetre drivers tuned for wide frequency response."
    )
    official = Source(
        channel=Channel.WEB,
        url="https://x.invalid/official",
        source_type=SourceType.OFFICIAL_DOC,
        raw_text=press_release + " Specifications follow in a long official table of values.",
    )
    copy_a = Source(
        channel=Channel.WEB, url="https://x.invalid/a", raw_text="Sony announced it. " + press_release
    )
    copy_b = Source(
        channel=Channel.WEB, url="https://x.invalid/b", raw_text="Announced this week. " + press_release
    )
    independent = Source(
        channel=Channel.WEB,
        url="https://x.invalid/independent",
        raw_text=(
            "We measured the headphones on our own test rig and found the clamping force gentle "
            "and the treble smoother than the previous generation."
        ),
    )

    report = cluster_sources([official, copy_a, copy_b, independent])

    assert official.independence_group_id == copy_a.independence_group_id == copy_b.independence_group_id
    assert independent.independence_group_id != official.independence_group_id
    assert report.manufacturer_group_id == official.independence_group_id
    assert report.group_count == 2


def test_clustering_is_deterministic_across_runs():
    def build():
        return [
            Source(id=f"s{i}", channel=Channel.WEB, url=f"https://x.invalid/{i}", raw_text=text)
            for i, text in enumerate(["alpha beta gamma delta epsilon zeta", "totally different words here now ok"])
        ]

    first = build()
    second = build()
    cluster_sources(first)
    cluster_sources(second)
    assert [s.independence_group_id for s in first] == [s.independence_group_id for s in second]


# ── extraction ─────────────────────────────────────────────────────────────


async def test_extraction_produces_grounded_typed_evidence(job_context):
    state = await _researched_state(job_context)
    result = await evidence_extraction_node(job_context, state)
    evidence = result["evidence"]
    passages = {passage.id: passage for passage in state["passages"]}

    assert len(evidence) >= 25
    for item in evidence:
        assert item.passage_id in passages
        assert grounded_in(item.text, passages[item.passage_id].text)
        assert item.topic
        assert item.research_job_id == job_context.job_id

    # Manufacturer marketing never counts as strong evidence.
    official = {
        source.id for source in state["sources"] if source.source_type == SourceType.OFFICIAL_DOC
    }
    assert all(item.strength.value != "STRONG" for item in evidence if item.source_id in official)


async def test_extraction_rejects_text_the_passage_never_contained(job_context, monkeypatch):
    state = await _researched_state(job_context)

    async def hallucinate(prompt, schema, *, task="", context=None):
        first = context["passages"][0]
        return EvidenceExtractionResult(
            items=[
                ExtractedEvidence(
                    passage_id=first["id"],
                    topic="Battery Life",
                    evidence_type="MEASUREMENT",
                    sentiment="POSITIVE",
                    strength="STRONG",
                    text="The battery lasted 400 hours in a NASA endurance laboratory.",
                ),
                ExtractedEvidence(
                    passage_id="not-a-real-passage-id",
                    topic="Battery Life",
                    evidence_type="FACT",
                    sentiment="POSITIVE",
                    strength="STRONG",
                    text=first["text"][:80],
                ),
            ]
        )

    monkeypatch.setattr(job_context.llm, "generate_structured", hallucinate)
    result = await evidence_extraction_node(job_context, state)
    assert result["evidence"] == []


async def test_repeated_agreement_across_groups_is_labelled_a_pattern(job_context):
    state = await _researched_state(job_context)
    evidence = (await evidence_extraction_node(job_context, state))["evidence"]
    assert any(item.evidence_type == EvidenceType.REPEATED_PATTERN for item in evidence)


async def test_a_failed_source_does_not_stop_the_channel(job_context):
    state = await _researched_state(job_context)
    failed = [s for s in state["sources"] if s.status == SourceStatus.FAILED]
    fetched = [s for s in state["sources"] if s.status == SourceStatus.FETCHED]
    assert failed, "the fixture includes one unfetchable source"
    assert failed[0].failure_reason
    assert len(fetched) >= 8
    assert state["channel_outcomes"]["WEB"]["status"] == "OK"
