"""Source independence clustering.

Three sources saying the same thing are only three pieces of evidence if they
found it out independently. Syndicated press releases, aggregator rewrites and
manufacturer-derived copy all trace back to one origin, so they share an
``independence_group_id`` and are collapsed to a single voice when confidence is
computed.

Two signals are used:

* **Textual reuse** — 5-gram containment (``overlap / min(len)``) catches a press
  release republished inside a longer page, which plain Jaccard misses; Jaccard
  catches two pages that are near-identical overall.
* **Manufacturer provenance** — anything whose text is largely reused from the
  official/manufacturer document joins the manufacturer's group, because it is
  not an independent observation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.domain import Source
from app.models.enums import SourceType
from app.services.heuristics import jaccard, shingles

CONTAINMENT_THRESHOLD = 0.6
JACCARD_THRESHOLD = 0.45


@dataclass
class ClusterReport:
    group_count: int
    clustered_source_ids: list[list[str]]
    manufacturer_group_id: str | None


class _UnionFind:
    def __init__(self, keys: list[str]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left


def containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def cluster_sources(sources: list[Source]) -> ClusterReport:
    """Assign ``independence_group_id`` to every source, in place."""

    usable = [source for source in sources if source.raw_text.strip()]
    if not usable:
        for source in sources:
            source.independence_group_id = source.independence_group_id or str(uuid.uuid4())
        return ClusterReport(group_count=len(sources), clustered_source_ids=[], manufacturer_group_id=None)

    fingerprints = {source.id: shingles(source.raw_text) for source in usable}
    union = _UnionFind([source.id for source in usable])

    for index, left in enumerate(usable):
        for right in usable[index + 1 :]:
            left_prints = fingerprints[left.id]
            right_prints = fingerprints[right.id]
            if (
                containment(left_prints, right_prints) >= CONTAINMENT_THRESHOLD
                or jaccard(left_prints, right_prints) >= JACCARD_THRESHOLD
            ):
                union.union(left.id, right.id)

    # Deterministic group ids, derived from the smallest member id in each group,
    # so a re-run of the same inputs produces the same grouping identifiers.
    members: dict[str, list[str]] = {}
    for source in usable:
        members.setdefault(union.find(source.id), []).append(source.id)

    group_ids: dict[str, str] = {}
    for root, member_ids in members.items():
        anchor = sorted(member_ids)[0]
        group_ids[root] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"proofly:independence:{anchor}"))

    manufacturer_group_id: str | None = None
    for source in usable:
        source.independence_group_id = group_ids[union.find(source.id)]
        if source.source_type == SourceType.OFFICIAL_DOC:
            manufacturer_group_id = source.independence_group_id

    for source in sources:
        if not source.independence_group_id:
            source.independence_group_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"proofly:independence:{source.id}")
            )

    clustered = [sorted(ids) for ids in members.values() if len(ids) > 1]
    return ClusterReport(
        group_count=len({source.independence_group_id for source in sources}),
        clustered_source_ids=sorted(clustered),
        manufacturer_group_id=manufacturer_group_id,
    )
