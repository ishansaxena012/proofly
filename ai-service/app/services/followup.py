"""Evidence-grounded follow-up Q&A (docs/API.md §POST .../followup).

The answer may only use evidence and claims the backend supplied for that job.
Three guards enforce it:

* retrieval is restricted to the supplied evidence — nothing else is reachable;
* returned citations are intersected with the supplied ids;
* any figure in the answer that does not appear in the cited evidence causes the
  generated answer to be discarded in favour of the deterministic, quote-only
  answer.

"There is insufficient evidence to answer that" is an acceptable answer.
"""

from __future__ import annotations

import logging
import re

from app.graph.prompts import followup_prompt
from app.graph.schemas import FollowupAnswer
from app.providers.base import LLMProvider
from app.providers.llm import TASK_FOLLOWUP, MockLLMProvider, cosine_similarity
from app.services.heuristics import content_words

log = logging.getLogger(__name__)

TOP_K = 8
MIN_RELEVANCE = 0.15
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

INSUFFICIENT = (
    "The evidence gathered for this research job does not address that question, so there is "
    "insufficient evidence to answer it."
)


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER_RE.finditer(text)}


async def _rank_evidence(
    llm: LLMProvider, question: str, evidence: list[dict]
) -> list[dict]:
    if not evidence:
        return []
    texts = [str(item.get("text", "")) for item in evidence]
    try:
        vectors = await llm.embed([question, *texts])
    except Exception as exc:  # noqa: BLE001 - retrieval falls back to lexical
        log.warning("follow-up embedding failed: %s", exc)
        vectors = []

    question_tokens = content_words(question)
    scored: list[tuple[float, int, dict]] = []
    for index, item in enumerate(evidence):
        item_tokens = content_words(str(item.get("text", ""))) | content_words(
            str(item.get("topic", ""))
        )
        overlap = len(question_tokens & item_tokens)
        if not overlap:
            # No shared content word: the evidence does not speak to the question.
            # Semantic similarity alone is not allowed to manufacture relevance.
            continue
        lexical = overlap / len(question_tokens) if question_tokens else 0.0
        semantic = 0.0
        if len(vectors) == len(evidence) + 1:
            semantic = cosine_similarity(vectors[0], vectors[index + 1])
        scored.append((0.6 * lexical + 0.4 * max(semantic, 0.0), index, item))

    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for score, _, item in scored[:TOP_K] if score >= MIN_RELEVANCE]


async def answer_followup(
    llm: LLMProvider,
    question: str,
    evidence: list[dict],
    claims: list[dict],
) -> tuple[str, list[str]]:
    question = (question or "").strip()
    if not question:
        return INSUFFICIENT, []

    valid_ids = {str(item.get("id")) for item in evidence if item.get("id")}
    relevant = await _rank_evidence(llm, question, evidence)
    if not relevant:
        return INSUFFICIENT, []

    relevant_ids = {str(item.get("id")) for item in relevant}
    related_claims = [
        claim
        for claim in claims
        if str(claim.get("topic", "")) in {str(item.get("topic", "")) for item in relevant}
    ]

    deterministic = await MockLLMProvider().generate_structured(
        "", FollowupAnswer, task=TASK_FOLLOWUP, context={"question": question, "evidence": relevant}
    )

    try:
        generated = await llm.generate_structured(
            followup_prompt(question, relevant, related_claims),
            FollowupAnswer,
            task=TASK_FOLLOWUP,
            context={"question": question, "evidence": relevant, "claims": related_claims},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("follow-up generation failed: %s", exc)
        return deterministic.answer, list(deterministic.cited_evidence_ids)

    answer = (generated.answer or "").strip()
    cited = [
        evidence_id
        for evidence_id in generated.cited_evidence_ids
        if evidence_id in valid_ids and evidence_id in relevant_ids
    ]
    if not answer:
        return deterministic.answer, list(deterministic.cited_evidence_ids)

    cited_text = " ".join(
        str(item.get("text", "")) for item in relevant if str(item.get("id")) in set(cited)
    )
    if not _numbers(answer) <= _numbers(cited_text):
        log.info("discarding follow-up answer containing figures absent from the cited evidence")
        return deterministic.answer, list(deterministic.cited_evidence_ids)

    if not cited:
        # An answer with no citation cannot be shown as evidence-grounded.
        return INSUFFICIENT, []

    return answer, cited
