"""Deterministic fixture datasets used by demo mode and by the tests.

Only the Sony WH-1000XM6 golden path exists. That is deliberate: if a demo-mode
run asks about any other product, the mock providers return *nothing* rather than
inventing plausible-looking material about a product we have no fixture for. An
empty result set flows through the normal pipeline and lands on "insufficient
evidence", which is a correct outcome (docs/ENGINEERING_RULES.md rule 4).
"""

from __future__ import annotations

import re

from app.fixtures import sony_wh1000xm6 as golden

__all__ = ["golden", "matches_golden_fixture", "all_fixture_urls"]

_GOLDEN_MARKERS = (
    ("sony", "wh-1000xm6"),
    ("sony", "wh1000xm6"),
    ("wh-1000xm6",),
    ("wh1000xm6",),
    ("xm6",),
)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def matches_golden_fixture(query: str) -> bool:
    """True when a query plausibly refers to the golden-path fixture product."""

    normalised = " " + _normalise(query).replace(" ", "") + " "
    plain = _normalise(query)
    for marker_set in _GOLDEN_MARKERS:
        if all(_normalise(marker).replace(" ", "") in normalised for marker in marker_set):
            return True
    return "wh 1000xm6" in plain


def all_fixture_urls() -> set[str]:
    return golden.all_fixture_urls()
