"""The layer contract (doc 10 A.5) — framework-free.

A *layer* is one modality's organism–organism graph on the node universe: an edge list
plus a coverage mask (which nodes the modality actually measured). Adding a modality means
adding one :class:`LayerFactory` — it fetches its data, builds edges + coverage, and returns
a :class:`BuiltLayer`. The registry (``ordina_retes.registry``) keys factories by ``layer_id``.

This module holds only the *contract* and the shared :func:`normalize` step; concrete
factories (phylogeny, metabolic, …) live in ``ordina_retes`` because they reach out to
Braidworks, and the sparse ``Multiplex`` assembled from built layers lives there too. Nothing
here imports Django, a web framework, or numpy — a layer is a plain, serializable value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from .sources import SourcePins
from .taxon import Rank
from .universe import NodeUniverse

# One undirected (or directed) weighted edge between two nodes, by taxid. After
# :func:`normalize`, ``weight`` is in [0, 1]; before it, it is the raw layer score.
Edge = tuple[int, int, float]


class LayerManifest(BaseModel):
    """What a built layer *is* — enough to reproduce and audit it, without the edges.

    Stored in Postgres (doc 10 A.6 ``layer_manifest``) while the numeric edges go to Parquet.
    ``layer_version`` is a content digest so a rebuild that changes inputs changes the id.
    """

    layer_id: str
    layer_version: str
    rank: Rank
    directed: bool = False
    determinism: str = "exact"  # doc 03: deterministic layers reproduce bitwise
    source_pins: dict[str, str] = {}
    params: dict[str, str] = {}


class Coverage(BaseModel):
    """Which nodes this layer measured — the per-layer mask behind the union node set (B5).

    An organism absent from ``measured`` is *unmeasured* in this layer (no data), which is
    different from "measured as dissimilar". Analyses run on the measured-induced subgraph.
    """

    rank: Rank
    measured: frozenset[int] = frozenset()

    def state(self, taxid: int) -> str:
        return "measured" if taxid in self.measured else "unmeasured"


class BuiltLayer(BaseModel):
    """A factory's output: the manifest, the (normalized) edges, and the coverage mask."""

    manifest: LayerManifest
    edges: list[Edge] = []
    coverage: Coverage


class LayerFactory(ABC):
    """Build one layer on a node universe. One subclass per modality (doc 10 A.5)."""

    layer_id: ClassVar[str]

    @abstractmethod
    def build(self, universe: NodeUniverse, sources: SourcePins) -> BuiltLayer:
        """Fetch this modality's data and return its edges + coverage on ``universe``."""


def normalize(edges: list[Edge]) -> list[Edge]:
    """Rank-normalize edge weights to [0, 1] over the measured edges (doc 03).

    Each weight becomes its fractional average rank among all edge weights, so layers built
    on incomparable raw scales (patristic distance, Jaccard, …) combine on one [0, 1] scale.
    Ties share their average rank; a single edge maps to 1.0. Edge order is preserved.
    """
    if not edges:
        return []
    weights = [w for _, _, w in edges]
    order = sorted(range(len(weights)), key=lambda i: weights[i])
    ranks = [0.0] * len(weights)
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and weights[order[j]] == weights[order[i]]:
            j += 1
        average_position = (i + j - 1) / 2.0
        for k in range(i, j):
            ranks[order[k]] = average_position
        i = j
    denom = (len(weights) - 1) or 1
    return [(a, b, ranks[idx] / denom) for idx, (a, b, _) in enumerate(edges)]
