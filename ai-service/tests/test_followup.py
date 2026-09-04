"""Follow-up Q&A must stay inside the evidence it was given."""

from __future__ import annotations

from app.graph.schemas import FollowupAnswer
from app.providers.llm import MockLLMProvider
from app.services.followup import INSUFFICIENT, answer_followup
from tests.factories import build_evidence

EVIDENCE = [
    {
        "id": item.id,
        "text": item.text,
        "topic": item.topic,
        "sourceId": item.source_id,
        "sentiment": item.sentiment.value,
    }
    for item in build_evidence("job")
]
CLAIMS = [
    {"id": "claim-1", "topic": "Microphone & Call Quality", "statement": "Reports are divided."}
]


async def test_answer_cites_only_supplied_evidence():
    llm = MockLLMProvider()
    answer, cited = await answer_followup(llm, "How is the microphone outdoors in wind?", EVIDENCE, CLAIMS)

    assert cited
    assert set(cited) <= {item["id"] for item in EVIDENCE}
    assert "wind" in answer.lower()


async def test_unanswerable_questions_return_insufficient_evidence():
    llm = MockLLMProvider()
    answer, cited = await answer_followup(
        llm, "Does it come with a titanium carrying case for scuba diving?", EVIDENCE, CLAIMS
    )
    assert answer == INSUFFICIENT
    assert cited == []


async def test_empty_question_is_rejected():
    answer, cited = await answer_followup(MockLLMProvider(), "   ", EVIDENCE, CLAIMS)
    assert answer == INSUFFICIENT
    assert cited == []


async def test_no_evidence_means_no_answer():
    answer, cited = await answer_followup(MockLLMProvider(), "How is the battery?", [], [])
    assert answer == INSUFFICIENT
    assert cited == []


class _FabricatingLLM(MockLLMProvider):
    async def generate_structured(self, prompt, schema, *, task="", context=None):
        if task == "followup":
            return FollowupAnswer(
                answer="It lasts 500 hours and includes a free 12 month subscription.",
                cited_evidence_ids=[str(context["evidence"][0]["id"])],
            )
        return await super().generate_structured(prompt, schema, task=task, context=context)


async def test_an_answer_with_invented_figures_is_discarded():
    answer, cited = await answer_followup(
        _FabricatingLLM(), "How is the battery life?", EVIDENCE, CLAIMS
    )
    assert "500 hours" not in answer
    assert set(cited) <= {item["id"] for item in EVIDENCE}


class _UncitedLLM(MockLLMProvider):
    async def generate_structured(self, prompt, schema, *, task="", context=None):
        if task == "followup":
            return FollowupAnswer(answer="Trust me, it is great.", cited_evidence_ids=[])
        return await super().generate_structured(prompt, schema, task=task, context=context)


async def test_an_uncited_answer_is_not_presented_as_grounded():
    answer, cited = await answer_followup(_UncitedLLM(), "How is the battery life?", EVIDENCE, CLAIMS)
    assert answer == INSUFFICIENT
    assert cited == []


class _ForeignCitationLLM(MockLLMProvider):
    async def generate_structured(self, prompt, schema, *, task="", context=None):
        if task == "followup":
            return FollowupAnswer(
                answer="The microphone struggles in wind.",
                cited_evidence_ids=["evidence-from-another-job"],
            )
        return await super().generate_structured(prompt, schema, task=task, context=context)


async def test_citations_outside_the_supplied_set_are_dropped():
    answer, cited = await answer_followup(
        _ForeignCitationLLM(), "How is the microphone in wind?", EVIDENCE, CLAIMS
    )
    assert cited == []
    assert answer == INSUFFICIENT
