"""Prompt construction.

Every prompt states the same non-negotiable rule: work only from the supplied
material. Prompts are built from the same context dictionaries handed to the
provider, so the live and deterministic paths always see identical inputs.
"""

from __future__ import annotations

import json

GROUNDING_RULE = (
    "You are an evidence analyst. Use ONLY the material provided below. Never invent "
    "sources, quotations, statistics, model names or numbers. If the material does not "
    "support an answer, say so explicitly. Preserve disagreement between sources; never "
    "average conflicting reports into a consensus."
)


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def product_resolution_prompt(query: str) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: identify the single specific product a user is asking about.\n"
        "If the query names a product category, a superlative ('best ...'), several "
        "candidate products, or a brand without a model, it is AMBIGUOUS: set "
        "ambiguous=true and explain why. Do not guess a specific model.\n"
        "Do not list example product names you are not certain exist.\n\n"
        f"User query: {query!r}\n"
    )


def plan_extension_prompt(product: str, category: str, existing: list[str]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: propose at most three ADDITIONAL research dimensions that a buyer of this "
        "specific product would care about and that are not already covered.\n"
        "Return an empty list if nothing important is missing.\n\n"
        f"Product: {product}\nCategory: {category}\n"
        f"Dimensions already planned: {_json(existing)}\n"
    )


def evidence_extraction_prompt(product: str, passages: list[dict], dimensions: list[dict]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: extract discrete pieces of evidence about the product from the passages.\n"
        "Rules:\n"
        "- Every item's `text` MUST be copied verbatim from the passage it came from.\n"
        "- `passage_id` MUST be one of the ids supplied.\n"
        "- `topic` MUST be one of the supplied dimension names.\n"
        "- `evidence_type` is one of FACT, SPECIFICATION, EXPERT_OPINION, "
        "CUSTOMER_EXPERIENCE, REPEATED_PATTERN, ANECDOTE, COMPARISON, MEASUREMENT, CLAIM.\n"
        "- `sentiment` is one of POSITIVE, NEGATIVE, NEUTRAL, MIXED.\n"
        "- `strength` is one of STRONG, MODERATE, WEAK. Manufacturer marketing about its own "
        "product is never STRONG.\n"
        "- Skip passages that say nothing evaluative or factual about the product.\n\n"
        f"Product: {product}\n"
        f"Dimensions: {_json([d['name'] for d in dimensions])}\n"
        f"Passages: {_json(passages)}\n"
    )


def claim_generation_prompt(product: str, topic: str, evidence: list[dict]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: write the claims about this one topic that the evidence actually supports.\n"
        "Rules:\n"
        "- Reference evidence only by the ids supplied.\n"
        "- Any number in a claim must appear in the evidence you cite for it.\n"
        "- If evidence disagrees, write ONE claim that states the disagreement and cite the "
        "supporting ids and the contradicting ids. Do not pick a winner.\n"
        "- Keep wording no stronger than the evidence warrants.\n\n"
        f"Product: {product}\nTopic: {topic}\n"
        f"Evidence: {_json(evidence)}\n"
    )


def conflict_explanation_prompt(topic: str, positive: list[str], negative: list[str]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: explain why these two groups of reports disagree, using only conditions that "
        "the quoted text itself mentions (environment, usage, configuration, time period).\n"
        "If the text names no such condition, say the split is unexplained. Never declare one "
        "side correct.\n\n"
        f"Topic: {topic}\n"
        f"Positive reports: {_json(positive)}\n"
        f"Negative reports: {_json(negative)}\n"
    )


def verification_prompt(product: str, claims: list[dict]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: check each claim against the evidence quoted with it and flag any claim whose "
        "wording is stronger than its evidence (absolutes, generalisation from one report, "
        "numbers not present in the evidence, causal language the evidence does not show).\n"
        "Set overstated=true and list the issues; suggest a more cautious revised_statement "
        "that keeps only what the evidence shows.\n\n"
        f"Product: {product}\nClaims: {_json(claims)}\n"
    )


def narrative_prompt(context: dict) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: write a short executive summary of this research run.\n"
        "Rules:\n"
        "- Use only the scores, counts and topic names supplied; introduce no new numbers.\n"
        "- Say plainly where sources disagree.\n"
        "- If the run was produced in demo mode, say so in the first sentence.\n"
        "- Do not express certainty the confidence value does not support.\n\n"
        f"{_json(context)}\n"
    )


def followup_prompt(question: str, evidence: list[dict], claims: list[dict]) -> str:
    return (
        f"{GROUNDING_RULE}\n\n"
        "Task: answer the user's question using ONLY the evidence and claims below.\n"
        "Rules:\n"
        "- Cite the evidence ids you used in cited_evidence_ids.\n"
        "- If the evidence does not answer the question, say that there is insufficient "
        "evidence and cite nothing.\n"
        "- Introduce no facts, numbers or product details that are not in the evidence.\n\n"
        f"Question: {question!r}\n"
        f"Evidence: {_json(evidence)}\n"
        f"Claims: {_json(claims)}\n"
    )
