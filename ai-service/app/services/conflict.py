"""When does disagreement count as a conflict?

Conflicts are never averaged away, but not every dissenting sentence is a
conflict either: one outlier against seven independent reports is an outlier, and
calling it "sources are divided" would be its own kind of distortion.

A side counts as substantial when it is attested by at least two independent
source groups, or when a lone voice carries STRONG evidence (a measurement, a
specification). A conflict exists when both sides are substantial and together
they span at least two independent groups.

Both the claim generator and the conflict detector use this one definition, so a
report can never say "divided" in a claim while omitting the conflict.
"""

from __future__ import annotations

MIN_GROUPS_PER_SIDE = 2


def side_is_substantial(group_count: int, has_strong_evidence: bool) -> bool:
    return group_count >= MIN_GROUPS_PER_SIDE or has_strong_evidence


def is_genuine_conflict(
    positive_groups: set[str],
    negative_groups: set[str],
    *,
    positive_has_strong: bool = False,
    negative_has_strong: bool = False,
) -> bool:
    if not positive_groups or not negative_groups:
        return False
    if len(positive_groups | negative_groups) < 2:
        return False
    return side_is_substantial(len(positive_groups), positive_has_strong) and side_is_substantial(
        len(negative_groups), negative_has_strong
    )
