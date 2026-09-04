"""Deterministic evaluation harness for the golden-path fixture (spec §46).

Runs the full research graph over the Sony WH-1000XM6 fixture with every provider
mocked and no network access, then asserts the properties that make a Proofly
report trustworthy:

1. every evidence id cited anywhere in the report exists in the evidence store;
2. every claim carries at least one evidence relationship, unless it is
   ``INSUFFICIENT_EVIDENCE``;
3. the known context-dependent conflict (microphone: indoors vs. outdoors)
   survives into ``report.conflicts`` with both positions and their evidence;
4. no source URL in the report was invented — every one is a fixture URL.

Run with::

    python -m eval.run_eval          # from the ai-service directory

Exit code 0 = all checks passed.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field

import httpx

from app.config import Settings
from app.fixtures import all_fixture_urls
from app.graph.budget import ResearchBudget
from app.graph.context import JobContext
from app.graph.pipeline import build_graph
from app.graph.state import initial_state
from app.models.enums import ClaimStatus, JobStatus
from app.providers.factory import build_providers
from app.services.backend_client import BackendClient

EVAL_JOB_ID = "00000000-0000-4000-8000-0000000e7a10"
GOLDEN_QUERY = "Sony WH-1000XM6"
KNOWN_CONFLICT_TOPIC = "Microphone & Call Quality"


@dataclass
class EvalResult:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))

    @property
    def passed(self) -> bool:
        return all(passed for _, passed, _ in self.checks)

    def render(self) -> str:
        lines = []
        for name, passed, detail in self.checks:
            marker = "PASS" if passed else "FAIL"
            lines.append(f"[{marker}] {name}" + (f" — {detail}" if detail else ""))
        total = len(self.checks)
        failed = sum(1 for _, passed, _ in self.checks if not passed)
        lines.append("")
        lines.append(f"{total - failed}/{total} checks passed")
        return "\n".join(lines)


def _offline_backend(settings: Settings) -> BackendClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(
        base_url=settings.backend_internal_url,
        transport=httpx.MockTransport(handler),
        headers={"X-Internal-Key": settings.internal_api_key},
    )
    return BackendClient(settings, client=client)


def _eval_settings() -> Settings:
    return Settings(
        demo_mode=True,
        internal_api_key="eval-internal-key",
        backend_internal_url="http://backend.invalid",
        redis_url="",
        gemini_api_key="",
        youtube_api_key="",
        search_provider="mock",
    )


async def run_golden_pipeline() -> dict:
    settings = _eval_settings()
    providers = build_providers(settings, demo_mode=True)
    backend = _offline_backend(settings)
    ctx = JobContext.create(
        job_id=EVAL_JOB_ID,
        product_query=GOLDEN_QUERY,
        demo_mode=True,
        settings=settings,
        providers=providers,
        backend=backend,
        budget=ResearchBudget(settings),
    )
    graph = build_graph(ctx)
    try:
        return await graph.ainvoke(
            initial_state(EVAL_JOB_ID, GOLDEN_QUERY, True),
            config={"configurable": {"thread_id": EVAL_JOB_ID}, "recursion_limit": 60},
        )
    finally:
        await providers.aclose()


def evaluate(state: dict) -> EvalResult:
    result = EvalResult()

    report = state.get("report")
    result.record("A report was produced", report is not None)
    if report is None:
        return result

    result.record(
        "Job reached a successful terminal state",
        state.get("terminal_status")
        in (JobStatus.COMPLETED.value, JobStatus.PARTIALLY_COMPLETED.value),
        str(state.get("terminal_status")),
    )

    evidence_ids = {item.id for item in state.get("evidence", [])}
    result.record("Evidence store is non-empty", bool(evidence_ids), f"{len(evidence_ids)} items")

    # 1. Every cited evidence id exists.
    cited: set[str] = set()
    for bucket in (
        report.key_strengths,
        report.key_weaknesses,
        report.common_praise,
        report.common_complaints,
    ):
        for item in bucket:
            cited.update(item.evidence_ids)
    if report.long_term_ownership:
        cited.update(report.long_term_ownership.evidence_ids)
    for conflict in report.conflicts:
        cited.update(conflict.position_a.evidence_ids)
        cited.update(conflict.position_b.evidence_ids)
    for claim in report.claims:
        cited.update(reference.id for reference in claim.supporting_evidence)
        cited.update(reference.id for reference in claim.contradicting_evidence)

    dangling = sorted(cited - evidence_ids)
    result.record(
        "Every cited evidence id exists in the evidence store",
        not dangling,
        f"{len(cited)} citations checked" if not dangling else f"dangling: {dangling[:5]}",
    )

    claim_ids = {claim.id for claim in report.claims}
    dangling_claims = sorted(
        {finding.claim_id for finding in report.key_findings} - claim_ids
    )
    result.record(
        "Every key finding points at a real claim",
        not dangling_claims,
        "" if not dangling_claims else f"dangling: {dangling_claims}",
    )

    # 2. Claims are backed by evidence or explicitly marked insufficient.
    unbacked = [
        claim.id
        for claim in report.claims
        if not (claim.supporting_evidence or claim.contradicting_evidence)
        and claim.status != ClaimStatus.INSUFFICIENT_EVIDENCE.value
    ]
    result.record(
        "Every claim has >=1 evidence relationship or is INSUFFICIENT_EVIDENCE",
        not unbacked,
        f"{len(report.claims)} claims checked" if not unbacked else f"unbacked: {unbacked[:5]}",
    )

    # 3. The known conflict survived.
    conflict_topics = [conflict.topic for conflict in report.conflicts]
    known = next(
        (c for c in report.conflicts if c.topic == KNOWN_CONFLICT_TOPIC), None
    )
    result.record(
        f"The known conflict ({KNOWN_CONFLICT_TOPIC}) is present in report.conflicts",
        known is not None,
        f"conflicts: {conflict_topics}",
    )
    if known is not None:
        result.record(
            "The known conflict keeps both positions with their evidence",
            bool(known.position_a.evidence_ids) and bool(known.position_b.evidence_ids),
            f"{len(known.position_a.evidence_ids)} vs {len(known.position_b.evidence_ids)}",
        )
        result.record(
            "The known conflict explains the split rather than resolving it",
            bool(known.explanation) and known.resolved is False,
            known.explanation[:120],
        )

    # 4. No hallucinated source URLs.
    allowed = all_fixture_urls()
    invented = sorted({source.url for source in report.sources} - allowed)
    result.record(
        "No source URL in the report was invented",
        not invented,
        f"{len(report.sources)} sources checked" if not invented else f"invented: {invented}",
    )

    # Extra integrity checks that are cheap and catch regressions.
    result.record(
        "Overall score is inside 0..100 and confidence inside 0..1",
        0 <= report.overall_score <= 100 and 0.0 <= report.confidence <= 1.0,
        f"score={report.overall_score} confidence={report.confidence}",
    )
    result.record(
        "Demo mode is disclosed in the report caveats",
        any("DEMO MODE" in caveat for caveat in report.caveats),
    )
    result.record(
        "Independence grouping collapsed the syndicated/manufacturer sources",
        len({source.independence_group_id for source in state.get("sources", [])})
        < len(state.get("sources", [])),
        f"{len({s.independence_group_id for s in state.get('sources', [])})} groups from "
        f"{len(state.get('sources', []))} sources",
    )
    return result


async def main() -> int:
    state = await run_golden_pipeline()
    result = evaluate(state)
    print(result.render())
    if "--json" in sys.argv:
        print(
            json.dumps(
                [
                    {"check": name, "passed": passed, "detail": detail}
                    for name, passed, detail in result.checks
                ],
                indent=2,
            )
        )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
