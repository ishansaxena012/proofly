"""LLM providers.

``GeminiLLMProvider`` is the only place in the codebase allowed to import a
generative-AI SDK. ``MockLLMProvider`` is a deterministic, network-free
implementation that produces schema-valid output derived *only* from the context
it is handed, which is what lets demo mode run the identical pipeline without
inventing anything.
"""

from __future__ import annotations

import asyncio
import logging
import math
import types as _pytypes
import typing
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from app.config import Settings
from app.fixtures import golden, matches_golden_fixture
from app.graph import schemas as s
from app.graph.catalog import CATEGORY_ALIASES, Dimension, resolve_category_key
from app.models.enums import Channel, Sentiment, SourceType
from app.providers.base import LLMProvider, ProviderError
from app.services import heuristics as h
from app.services.conflict import is_genuine_conflict

log = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 768

# Task identifiers. The live provider ignores these (its instructions are in the
# prompt); the mock dispatches on them.
TASK_PRODUCT_RESOLUTION = "product_resolution"
TASK_PLAN_EXTENSION = "plan_extension"
TASK_EVIDENCE_EXTRACTION = "evidence_extraction"
TASK_CLAIM_GENERATION = "claim_generation"
TASK_CONFLICT_EXPLANATION = "conflict_explanation"
TASK_VERIFICATION = "verification"
TASK_NARRATIVE = "narrative"
TASK_FOLLOWUP = "followup"


# ───────────────────────────── Gemini ──────────────────────────────────────


class GeminiLLMProvider(LLMProvider):
    """Live Gemini implementation (google-genai SDK)."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY is required for GeminiLLMProvider")
        try:
            from google import genai  # noqa: PLC0415 - deliberately lazy
        except ImportError as exc:  # pragma: no cover - exercised only without the SDK
            raise ProviderError(f"google-genai SDK is not installed: {exc}") from exc

        self._genai = genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._embedding_model = settings.gemini_embedding_model
        self._max_attempts = 3

    async def _with_retries(self, operation: str, func: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await func()
            except Exception as exc:  # noqa: BLE001 - SDK raises a wide variety
                last_error = exc
                if attempt == self._max_attempts:
                    break
                await asyncio.sleep(min(2 ** attempt, 8))
        raise ProviderError(f"Gemini {operation} failed: {last_error}") from last_error

    async def generate(self, prompt: str, *, task: str = "", context: dict | None = None) -> str:
        async def call() -> str:
            response = await self._client.aio.models.generate_content(
                model=self._model, contents=prompt
            )
            return (response.text or "").strip()

        return await self._with_retries(f"generate[{task or 'text'}]", call)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        task: str = "",
        context: dict | None = None,
    ) -> BaseModel:
        from google.genai import types as genai_types  # noqa: PLC0415

        async def call() -> BaseModel:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            if isinstance(parsed, dict):
                return schema.model_validate(parsed)
            return schema.model_validate_json(response.text or "{}")

        return await self._with_retries(f"generate_structured[{task or schema.__name__}]", call)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        async def call() -> list[list[float]]:
            response = await self._client.aio.models.embed_content(
                model=self._embedding_model, contents=texts
            )
            return [list(item.values or []) for item in (response.embeddings or [])]

        return await self._with_retries("embed", call)


# ───────────────────────────── Mock ────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """Deterministic, offline LLM stand-in.

    Every output is a function of the supplied ``context`` (i.e. of text that was
    actually fetched from a source) plus fixed rules. It never introduces facts,
    numbers, product names or quotes that were not present in its input.
    """

    name = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    # -- text -------------------------------------------------------------

    async def generate(self, prompt: str, *, task: str = "", context: dict | None = None) -> str:
        context = context or {}
        if task == TASK_NARRATIVE:
            return self._narrative(context).executive_summary
        # Deterministic, obviously-synthetic echo. Used only for non-report text.
        digest = h.stable_seed(task, prompt)
        return f"[deterministic-mock:{task or 'text'}:{digest % 100000}]"

    # -- structured -------------------------------------------------------

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        task: str = "",
        context: dict | None = None,
    ) -> BaseModel:
        context = context or {}
        handler = {
            TASK_PRODUCT_RESOLUTION: self._product_resolution,
            TASK_PLAN_EXTENSION: self._plan_extension,
            TASK_EVIDENCE_EXTRACTION: self._evidence_extraction,
            TASK_CLAIM_GENERATION: self._claim_generation,
            TASK_CONFLICT_EXPLANATION: self._conflict_explanation,
            TASK_VERIFICATION: self._verification,
            TASK_NARRATIVE: self._narrative,
            TASK_FOLLOWUP: self._followup,
        }.get(task)
        if handler is not None:
            result = handler(context)
            if isinstance(result, schema):
                return result
            return schema.model_validate(result.model_dump())
        return synthesize_schema_instance(schema, seed=h.stable_seed(task, prompt))

    # -- embeddings -------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [deterministic_embedding(text) for text in texts]

    # -- handlers ---------------------------------------------------------

    def _product_resolution(self, context: dict) -> s.ProductResolutionLLM:
        query = str(context.get("query", "")).strip()
        if matches_golden_fixture(query):
            # The fixture dataset carries its own product metadata; reading it is
            # not invention. Any other product has no fixture, so we fall through
            # to pure parsing and stay silent about what we do not know.
            product = golden.PRODUCT
            return s.ProductResolutionLLM(
                canonical_name=product["canonical_name"],
                brand=product["brand"],
                category=product["category"],
                model=product["model"],
                ambiguous=False,
                ambiguity_reason="",
                clarification_options=[],
                confidence=0.95,
            )
        tokens = query.split()
        brand = ""
        known_brands = {
            "sony", "bose", "apple", "samsung", "sennheiser", "jbl", "anker", "dell", "lenovo",
            "hp", "asus", "acer", "google", "xiaomi", "oneplus", "nothing", "beyerdynamic",
            "audio-technica", "delonghi", "breville", "sage", "philips", "dyson",
        }
        for token in tokens:
            if token.lower().strip(",.") in known_brands:
                brand = token.strip(",.").title()
                break
        model = ""
        for token in tokens:
            stripped = token.strip(",.")
            if any(ch.isdigit() for ch in stripped) and any(ch.isalpha() for ch in stripped):
                model = stripped.upper()
                break
        category_key, matched = resolve_category_key(query)
        category = ""
        if matched:
            category = CATEGORY_ALIASES[category_key][0]
        elif model and brand:
            # A concrete brand+model with no category word in the query is still a
            # resolvable product; the planner will use the generic dimension set.
            category = ""
        confidence = 0.0
        if brand:
            confidence += 0.45
        if model:
            confidence += 0.45
        if matched:
            confidence += 0.1
        canonical = " ".join(part for part in (brand, model) if part) or query
        return s.ProductResolutionLLM(
            canonical_name=canonical,
            brand=brand,
            category=category,
            model=model,
            ambiguous=not (brand and model),
            ambiguity_reason=(
                "" if brand and model else "No single brand + model identifier detected in the query."
            ),
            clarification_options=[],
            confidence=round(min(confidence, 1.0), 3),
        )

    def _plan_extension(self, context: dict) -> s.PlanExtension:
        # The catalog is authoritative offline; the mock proposes no extra
        # dimensions rather than inventing category knowledge it does not have.
        return s.PlanExtension(dimensions=[])

    def _evidence_extraction(self, context: dict) -> s.EvidenceExtractionResult:
        dimensions = _dimensions_from_context(context)
        items: list[s.ExtractedEvidence] = []
        for passage in context.get("passages", []):
            text = str(passage.get("text", ""))
            source_type = SourceType(passage.get("source_type", SourceType.GENERIC.value))
            channel = Channel(passage.get("channel", Channel.WEB.value))
            authority = float(passage.get("authority", 0.5))
            for unit in _evidence_units(text):
                topic, score = h.topic_for(unit, dimensions)
                if not topic or score < 1:
                    continue
                sentiment = h.sentiment_for(unit)
                evidence_type = h.evidence_type_for(unit, source_type, channel)
                strength = h.strength_for(unit, source_type, evidence_type, authority)
                items.append(
                    s.ExtractedEvidence(
                        passage_id=str(passage.get("id", "")),
                        topic=topic,
                        evidence_type=evidence_type.value,
                        sentiment=sentiment.value,
                        strength=strength.value,
                        text=unit,
                    )
                )
        return s.EvidenceExtractionResult(items=items)

    def _claim_generation(self, context: dict) -> s.ClaimGenerationResult:
        topic = str(context.get("topic", "")).strip() or "General"
        evidence = list(context.get("evidence", []))
        if not evidence:
            return s.ClaimGenerationResult(claims=[])

        positive = [e for e in evidence if e.get("sentiment") == Sentiment.POSITIVE.value]
        negative = [e for e in evidence if e.get("sentiment") == Sentiment.NEGATIVE.value]
        mixed = [e for e in evidence if e.get("sentiment") == Sentiment.MIXED.value]
        neutral = [e for e in evidence if e.get("sentiment") == Sentiment.NEUTRAL.value]

        claims: list[s.GeneratedClaim] = []

        def excerpt(items: list[dict]) -> str:
            ranked = sorted(
                items,
                key=lambda e: (
                    {"STRONG": 0, "MODERATE": 1, "WEAK": 2}.get(e.get("strength", "MODERATE"), 1),
                    len(str(e.get("text", ""))) * -1,
                ),
            )
            text = str(ranked[0].get("text", "")).strip() if ranked else ""
            return (text[:200].rstrip() + "…") if len(text) > 200 else text

        if positive and negative and _genuine_conflict(positive, negative):
            claims.append(
                s.GeneratedClaim(
                    topic=topic,
                    statement=(
                        f"Reports about {topic} are divided: some sources describe it positively "
                        f"while others describe a clear problem, so the outcome appears to depend "
                        f"on usage conditions."
                    ),
                    supporting_evidence_ids=[e["id"] for e in positive],
                    contradicting_evidence_ids=[e["id"] for e in negative],
                    contextualizing_evidence_ids=[e["id"] for e in mixed + neutral],
                )
            )
        elif positive and negative:
            majority, minority, direction = (
                (positive, negative, "a strength")
                if len(positive) >= len(negative)
                else (negative, positive, "a weakness")
            )
            claims.append(
                s.GeneratedClaim(
                    topic=topic,
                    statement=(
                        f"Sources mostly describe {topic} as {direction}, though at least one "
                        f'report says the opposite. Representative evidence: "{excerpt(majority)}"'
                    ),
                    supporting_evidence_ids=[e["id"] for e in majority],
                    contradicting_evidence_ids=[e["id"] for e in minority],
                    contextualizing_evidence_ids=[e["id"] for e in mixed + neutral],
                )
            )
        elif positive:
            claims.append(
                s.GeneratedClaim(
                    topic=topic,
                    statement=(
                        f"Sources consistently describe {topic} as a strength. "
                        f'Representative evidence: "{excerpt(positive)}"'
                    ),
                    supporting_evidence_ids=[e["id"] for e in positive],
                    contradicting_evidence_ids=[],
                    contextualizing_evidence_ids=[e["id"] for e in mixed + neutral],
                )
            )
        elif negative:
            claims.append(
                s.GeneratedClaim(
                    topic=topic,
                    statement=(
                        f"Sources consistently describe {topic} as a weakness. "
                        f'Representative evidence: "{excerpt(negative)}"'
                    ),
                    supporting_evidence_ids=[e["id"] for e in negative],
                    contradicting_evidence_ids=[],
                    contextualizing_evidence_ids=[e["id"] for e in mixed + neutral],
                )
            )
        else:
            claims.append(
                s.GeneratedClaim(
                    topic=topic,
                    statement=(
                        f"Available material on {topic} is descriptive rather than evaluative. "
                        f'Representative evidence: "{excerpt(neutral + mixed)}"'
                    ),
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    contextualizing_evidence_ids=[e["id"] for e in evidence],
                )
            )
        return s.ClaimGenerationResult(claims=claims)

    def _conflict_explanation(self, context: dict) -> s.ConflictExplanation:
        positive_texts = [str(t) for t in context.get("positive_texts", [])]
        negative_texts = [str(t) for t in context.get("negative_texts", [])]
        positive_context = _dominant_qualifiers(positive_texts)
        negative_context = _dominant_qualifiers(negative_texts)
        topic = str(context.get("topic", "this topic"))

        if positive_context and negative_context and positive_context != negative_context:
            explanation = (
                f"Context-dependent rather than contradictory: positive reports about {topic} are "
                f"associated with {positive_context}, while negative reports are associated with "
                f"{negative_context}. Both are preserved because they describe different conditions."
            )
            return s.ConflictExplanation(explanation=explanation, resolved=False)
        explanation = (
            f"Sources disagree about {topic} and the available evidence does not identify a "
            f"condition that explains the split. Both positions are preserved."
        )
        return s.ConflictExplanation(explanation=explanation, resolved=False)

    def _verification(self, context: dict) -> s.VerificationResult:
        verdicts: list[s.VerificationVerdict] = []
        absolutes = ("always", "never", "every user", "all users", "guaranteed", "proven", "universally")
        for claim in context.get("claims", []):
            statement = str(claim.get("statement", ""))
            lowered = f" {statement.lower()} "
            issues = [f"Absolute wording '{word}' is stronger than the evidence." for word in absolutes if word in lowered]
            verdicts.append(
                s.VerificationVerdict(
                    claim_id=str(claim.get("id", "")),
                    overstated=bool(issues),
                    issues=issues,
                    revised_statement="",
                )
            )
        return s.VerificationResult(verdicts=verdicts)

    def _narrative(self, context: dict) -> s.NarrativeSummary:
        product = str(context.get("product", "the product"))
        overall = context.get("overall_score")
        confidence = context.get("confidence")
        strengths = [str(x) for x in context.get("strengths", [])]
        weaknesses = [str(x) for x in context.get("weaknesses", [])]
        conflicts = [str(x) for x in context.get("conflict_topics", [])]
        source_count = int(context.get("source_count", 0))
        group_count = int(context.get("independent_group_count", 0))
        demo = bool(context.get("demo_mode", False))

        parts: list[str] = []
        if demo:
            parts.append(
                "This report was produced in DEMO MODE from Proofly's deterministic local "
                "fixture dataset. It is not live research and its sources are labelled demo "
                "fixtures."
            )
        parts.append(
            f"{product} was assessed from {source_count} source(s) across "
            f"{group_count} independent source group(s)."
        )
        if overall is not None and confidence is not None:
            parts.append(
                f"The derived overall score is {overall}/100 at {float(confidence):.2f} confidence; "
                f"both are computed from evidence quality, source independence and agreement, not "
                f"asserted by a language model."
            )
        if strengths:
            parts.append("Strongest areas: " + ", ".join(strengths[:3]) + ".")
        if weaknesses:
            parts.append("Weakest areas: " + ", ".join(weaknesses[:3]) + ".")
        if conflicts:
            parts.append(
                "Sources genuinely disagree about: "
                + ", ".join(conflicts)
                + ". Those disagreements are reported as conflicts rather than averaged away."
            )
        else:
            parts.append("No unresolved conflicts between sources were detected.")

        buy = [str(x) for x in context.get("who_should_buy", [])]
        avoid = [str(x) for x in context.get("who_should_avoid", [])]
        return s.NarrativeSummary(
            executive_summary=" ".join(parts),
            who_should_buy=buy,
            who_should_avoid=avoid,
        )

    def _followup(self, context: dict) -> s.FollowupAnswer:
        question = str(context.get("question", ""))
        evidence = list(context.get("evidence", []))
        question_tokens = set(h.words(question))
        scored: list[tuple[float, dict]] = []
        for item in evidence:
            text_tokens = set(h.words(str(item.get("text", ""))))
            topic_tokens = set(h.words(str(item.get("topic", ""))))
            overlap = len(question_tokens & (text_tokens | topic_tokens))
            if overlap:
                scored.append((overlap / max(len(question_tokens), 1), item))
        scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("id", ""))))
        top = [item for _, item in scored[:4]]
        if not top:
            return s.FollowupAnswer(
                answer=(
                    "The evidence gathered for this job does not address that question, so there "
                    "is insufficient evidence to answer it."
                ),
                cited_evidence_ids=[],
            )
        lines = [
            "Based only on the evidence collected for this job:",
        ]
        for item in top:
            lines.append(f"- [{item.get('topic')}] \"{str(item.get('text', '')).strip()}\"")
        return s.FollowupAnswer(
            answer="\n".join(lines),
            cited_evidence_ids=[str(item.get("id")) for item in top],
        )


# ───────────────────────────── helpers ─────────────────────────────────────


def _dimensions_from_context(context: dict) -> list[Dimension]:
    dimensions: list[Dimension] = []
    for entry in context.get("dimensions", []):
        dimensions.append(
            Dimension(
                name=str(entry.get("name", "")),
                rationale=str(entry.get("rationale", "")),
                keywords=tuple(str(k) for k in entry.get("keywords", ())),
            )
        )
    return dimensions


def _evidence_units(text: str) -> list[str]:
    """Split passage text into evidence-sized units (sentences, merged if tiny)."""

    units: list[str] = []
    buffer = ""
    for sentence in h.sentences(text):
        if len(sentence.split()) < 6 and buffer:
            buffer = f"{buffer} {sentence}"
            continue
        if buffer:
            units.append(buffer.strip())
        buffer = sentence
    if buffer:
        units.append(buffer.strip())
    return [unit for unit in units if len(unit.split()) >= 5]


def _dominant_qualifiers(texts: list[str]) -> str:
    return h.dominant_qualifiers(texts)


def _genuine_conflict(positive: list[dict], negative: list[dict]) -> bool:
    """Same conflict definition the graph uses, applied to evidence payloads."""

    def groups(items: list[dict]) -> set[str]:
        return {str(item.get("independence_group_id") or item.get("source_id")) for item in items}

    def has_strong(items: list[dict]) -> bool:
        return any(item.get("strength") == "STRONG" for item in items)

    return is_genuine_conflict(
        groups(positive),
        groups(negative),
        positive_has_strong=has_strong(positive),
        negative_has_strong=has_strong(negative),
    )


def deterministic_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """A stable pseudo-embedding: identical text always yields an identical vector,
    and lexically similar text yields similar vectors (bag-of-words hashing)."""

    vector = [0.0] * dimensions
    tokens = h.words(text)
    if not tokens:
        return vector
    for token in tokens:
        seed = h.stable_seed(token)
        index = seed % dimensions
        sign = 1.0 if (seed >> 17) & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def synthesize_schema_instance(schema: type[BaseModel], seed: int = 0) -> BaseModel:
    """Build a deterministic, schema-valid instance of an arbitrary model.

    This is the generic fallback for any structured task the mock does not have a
    dedicated handler for. It fills required fields with neutral, obviously
    synthetic values so the pipeline never crashes in demo mode.
    """

    values: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        values[name] = _synthesize_value(field.annotation, seed, name)
    return schema.model_validate(values)


def _synthesize_value(annotation: Any, seed: int, field_name: str) -> Any:
    origin = get_origin(annotation)
    if origin in (Union, _pytypes.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if not args:
            return None
        return _synthesize_value(args[0], seed, field_name)
    if origin is Literal:
        return get_args(annotation)[0]
    if origin in (list, set, tuple, typing.Sequence):
        return []
    if origin is dict:
        return {}
    if annotation is None or annotation is type(None):
        return None
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return synthesize_schema_instance(annotation, seed)
        if issubclass(annotation, bool):
            return False
        if issubclass(annotation, int):
            return 0
        if issubclass(annotation, float):
            return 0.0
        if issubclass(annotation, str):
            return f"deterministic-mock:{field_name}:{seed % 100000}"
    return None
