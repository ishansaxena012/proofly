"""The evaluation harness itself is part of the deliverable, so it is tested."""

from __future__ import annotations

from eval.run_eval import evaluate, run_golden_pipeline


async def test_golden_fixture_passes_every_evaluation_check():
    state = await run_golden_pipeline()
    result = evaluate(state)
    failures = [(name, detail) for name, passed, detail in result.checks if not passed]
    assert not failures, f"evaluation failures: {failures}"
    assert result.passed
    assert len(result.checks) >= 12


async def test_evaluation_detects_a_dangling_citation():
    state = await run_golden_pipeline()
    # Simulate a regression: a report citing evidence that is not in the store.
    state["report"].key_strengths[0].evidence_ids.append("evidence-that-does-not-exist")
    result = evaluate(state)
    assert not result.passed
    assert any(
        "cited evidence id exists" in name and not passed for name, passed, _ in result.checks
    )


async def test_evaluation_detects_an_invented_source_url():
    state = await run_golden_pipeline()
    state["report"].sources[0].url = "https://totally-made-up-review-site.example.com/xm6"
    result = evaluate(state)
    assert not result.passed
    assert any("invented" in name and not passed for name, passed, _ in result.checks)


async def test_evaluation_detects_a_dropped_conflict():
    state = await run_golden_pipeline()
    state["report"].conflicts.clear()
    result = evaluate(state)
    assert not result.passed
    assert any("known conflict" in name and not passed for name, passed, _ in result.checks)


async def test_evaluation_renders_a_readable_summary():
    state = await run_golden_pipeline()
    rendered = evaluate(state).render()
    assert "[PASS]" in rendered
    assert "checks passed" in rendered
