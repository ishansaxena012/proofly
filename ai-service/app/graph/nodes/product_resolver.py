"""Node 1 — product resolution.

Proofly researches ONE specific product. A query that names a category, a
superlative, several candidates, or a brand with no model cannot be resolved to
one product, and guessing would silently research something the user did not ask
about. Such a query short-circuits the graph with a clarification-needed failure.
"""

from __future__ import annotations

import logging
import re

from app.graph.catalog import CATEGORY_ALIASES, resolve_category_key
from app.graph.context import JobContext
from app.graph.prompts import product_resolution_prompt
from app.graph.schemas import ProductResolutionLLM
from app.graph.state import ResearchState
from app.models.domain import ProductResolution
from app.models.enums import ErrorCode, EventType, JobStatus
from app.providers.llm import TASK_PRODUCT_RESOLUTION

log = logging.getLogger(__name__)

# Words that mean "help me choose", not "research this product".
SHOPPING_MARKERS = (
    " best ", " top ", " greatest ", " cheapest ", " recommend ", " recommendation ",
    " recommendations ", " which ", " what should ", " should i buy ", " suggest ",
    " suggestions ", " options ", " alternatives ", " compare ", " comparison ",
    " under $", " under £", " budget ", " any good ",
)
MULTI_PRODUCT_MARKERS = (" vs ", " vs. ", " versus ", " or ")

# Tokens that describe a kind of thing rather than a particular product.
GENERIC_QUALIFIERS = {
    "wireless", "bluetooth", "noise", "noise-cancelling", "cancelling", "canceling", "anc",
    "over", "ear", "over-ear", "on-ear", "in-ear", "true", "smart", "portable", "gaming",
    "new", "latest", "pro", "premium", "cheap", "affordable", "the", "a", "an", "for", "with",
    "and", "of", "my", "me", "please", "review", "reviews",
}

KNOWN_BRANDS = {
    "sony", "bose", "apple", "airpods", "samsung", "sennheiser", "jbl", "anker", "soundcore",
    "dell", "lenovo", "hp", "asus", "acer", "razer", "microsoft", "google", "pixel", "xiaomi",
    "oneplus", "nothing", "beyerdynamic", "audio-technica", "shure", "sonos", "bowers",
    "delonghi", "breville", "sage", "philips", "dyson", "nespresso", "gaggia", "ninja",
    "instant", "logitech", "steelseries", "framework", "macbook", "iphone", "galaxy",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")


def _tokens(query: str) -> list[str]:
    return _TOKEN_RE.findall(query.lower())


def detect_ambiguity(query: str) -> tuple[bool, str, list[str]]:
    """Deterministic ambiguity detection. Returns (ambiguous, reason, guidance)."""

    lowered = f" {query.lower().strip()} "
    if not query.strip():
        return True, "The query is empty.", _guidance()

    for marker in SHOPPING_MARKERS:
        if marker in lowered:
            return (
                True,
                f"The query reads as a shopping/comparison request (matched {marker.strip()!r}) "
                f"rather than one specific product. Proofly researches exactly one product.",
                _guidance(),
            )
    for marker in MULTI_PRODUCT_MARKERS:
        if marker in lowered:
            return (
                True,
                "The query appears to name more than one product. Proofly researches exactly "
                "one product per job.",
                _guidance(),
            )

    tokens = _tokens(query)
    category_key, category_matched = resolve_category_key(query)
    category_tokens: set[str] = set()
    if category_matched:
        for alias in CATEGORY_ALIASES[category_key]:
            category_tokens.update(alias.split())

    brand_tokens = [token for token in tokens if token in KNOWN_BRANDS]
    distinctive = [
        token
        for token in tokens
        if token not in GENERIC_QUALIFIERS
        and token not in category_tokens
        and token not in KNOWN_BRANDS
    ]
    has_digit_token = any(any(char.isdigit() for char in token) for token in tokens)

    if not brand_tokens and not has_digit_token and not distinctive:
        return (
            True,
            "The query names a product category but no specific product.",
            _guidance(),
        )
    if not brand_tokens and not has_digit_token:
        return (
            True,
            "No brand or model identifier was found, so the query cannot be resolved to one "
            "specific product.",
            _guidance(),
        )
    if brand_tokens and not has_digit_token and not distinctive:
        return (
            True,
            f"The query names the brand {brand_tokens[0]!r} and a product category but no "
            f"specific model.",
            _guidance(),
        )
    return False, "", []


def _guidance() -> list[str]:
    """Clarification guidance.

    Deliberately instructions, not example product names: suggesting models we
    have not verified exist would be fabrication.
    """

    return [
        "Include the exact brand and model designation, for example 'Brand ModelNumber'.",
        "Research one product per job; submit separate jobs to look at alternatives.",
        "Copy the product name from the retailer or manufacturer listing if unsure.",
    ]


def _parse_identifiers(query: str) -> tuple[str, str]:
    brand = ""
    model = ""
    for raw in query.split():
        token = raw.strip(",.;:()[]")
        if not token:
            continue
        if not brand and token.lower() in KNOWN_BRANDS:
            brand = token.title()
        if not model and any(char.isdigit() for char in token) and len(token) > 1:
            model = token.upper()
    return brand, model


async def product_resolver_node(ctx: JobContext, state: ResearchState) -> dict:
    ctx.budget.check_deadline()
    query = state["product_query"]

    await ctx.backend.post_status(ctx.job_id, JobStatus.IDENTIFYING_PRODUCT)

    ambiguous, reason, guidance = detect_ambiguity(query)

    llm_result = await ctx.llm.generate_structured(
        product_resolution_prompt(query),
        ProductResolutionLLM,
        task=TASK_PRODUCT_RESOLUTION,
        context={"query": query},
    )

    brand, model = _parse_identifiers(query)
    brand = brand or (llm_result.brand or "").strip()
    model = model or (llm_result.model or "").strip()
    category_key, category_matched = resolve_category_key(query, llm_result.category)
    category = (llm_result.category or "").strip()
    if not category and category_matched:
        category = CATEGORY_ALIASES[category_key][0]

    if not ambiguous and llm_result.ambiguous and not (brand and model):
        # The deterministic check passed but the model is unsure and we have no
        # brand+model pair to fall back on: prefer asking over guessing.
        ambiguous = True
        reason = llm_result.ambiguity_reason or (
            "The product could not be resolved to a single specific model."
        )
        guidance = guidance or _guidance()

    canonical = (llm_result.canonical_name or "").strip() or query.strip()

    product = ProductResolution(
        raw_query=query,
        canonical_name=None if ambiguous else canonical,
        brand=brand or None,
        category=category or None,
        model=model or None,
        resolution_confidence=0.0 if ambiguous else max(float(llm_result.confidence), 0.5),
        ambiguous=ambiguous,
        ambiguity_reason=reason or None,
        clarification_options=guidance,
    )

    if ambiguous:
        message = (
            f"Could not resolve {query!r} to one specific product: {reason} "
            f"Please re-run with a specific brand and model."
        )
        log.info("job %s ambiguous product query: %s", ctx.job_id, reason)
        await ctx.backend.post_event(
            ctx.job_id,
            EventType.JOB_FAILED,
            message,
            {
                "errorCode": ErrorCode.INVALID_PRODUCT.value,
                "clarificationOptions": guidance,
                "rawQuery": query,
            },
        )
        await ctx.backend.post_status(
            ctx.job_id,
            JobStatus.FAILED,
            current_stage=JobStatus.IDENTIFYING_PRODUCT.value,
            error_code=ErrorCode.INVALID_PRODUCT.value,
            error_message=message,
        )
        return {
            "product": product,
            "clarification_needed": True,
            "terminal_status": JobStatus.FAILED.value,
            "error_code": ErrorCode.INVALID_PRODUCT.value,
            "error_message": message,
        }

    await ctx.backend.post_product(ctx.job_id, product)
    await ctx.backend.post_event(
        ctx.job_id,
        EventType.PRODUCT_IDENTIFIED,
        f"Resolved product: {product.canonical_name}",
        {
            "canonicalName": product.canonical_name,
            "brand": product.brand,
            "category": product.category,
            "model": product.model,
            "resolutionConfidence": round(product.resolution_confidence, 4),
        },
    )
    return {"product": product, "clarification_needed": False}


def route_after_resolution(state: ResearchState) -> str:
    return "clarification" if state.get("clarification_needed") else "planner"
