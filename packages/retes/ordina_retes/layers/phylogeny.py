"""PhylogenyLayer — the GTDB phylogeny control layer (doc 03 §3.3, doc 10 Slice 1).

The one layer whose Braidworks fetch is *pairwise* in spirit: it pulls each organism's
placement on the GTDB reference tree (``gtdb.tree.rootpath``) and turns pairs of placements
into patristic-distance edges. Braidworks stays per-entity — the pairwise reduction is
``gtdb_weaver.cophenetic`` — so this factory fetches once per species leaf, then aggregates.

Rank rule (B1, genus-primary): tree leaves are species representatives, so a **genus–genus**
edge is the aggregate patristic distance over the two genera's placed child species (mean by
default; ``aggregation="min"`` for closest-representative). Proximity is ``1 − dist/maxdist``
so closer genera score higher; :func:`normalize` then rank-maps every edge onto [0, 1] — which,
being monotonic in distance, makes the exact normalizer irrelevant to the final ranking. This
is the **control/null** layer: related organisms trivially look alike, and every real finding
must beat it (doc 09 §5).
"""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from statistics import fmean
from typing import Any

import braidworks
from gtdb_weaver import cophenetic
from ordina_core import (
    BuiltLayer,
    Coverage,
    Edge,
    LayerFactory,
    LayerManifest,
    NodeUniverse,
    SourcePins,
    normalize,
)

from ..registry import register

_WANT = "gtdb.tree.rootpath"


@register
class PhylogenyLayer(LayerFactory):
    """Build the genus-rank GTDB phylogeny layer from tree placements."""

    layer_id = "phylogeny.gtdb"

    def __init__(
        self,
        *,
        registry: Any | None = None,
        aggregation: str = "mean",
        threshold: float = 0.0,
    ) -> None:
        # ``registry`` overrides Braidworks' entry-point discovery — the seam that lets a
        # test inject the offline fixture weaver. ``aggregation`` and ``threshold`` are the
        # declared aggregation_rule / sparsification knobs (doc 03 §3.3).
        if aggregation not in ("mean", "min"):
            raise ValueError(f"aggregation must be 'mean' or 'min', got {aggregation!r}")
        self._registry = registry
        self._aggregation = aggregation
        self._threshold = threshold

    def build(self, universe: NodeUniverse, sources: SourcePins) -> BuiltLayer:
        rank = "genus"
        species = universe.species()
        result = braidworks.fetch(
            _WANT, ids=[str(t.taxid) for t in species], registry=self._registry
        )
        placements = {
            int(taxid): values[_WANT]
            for taxid, values in result.resolved.items()
            if _WANT in values
        }

        # Group each placed species' root path under its parent genus (B1 dual-rank).
        parent_of = {t.taxid: t.parent_genus for t in species}
        by_genus: dict[int, list[Any]] = {}
        for species_taxid, path in placements.items():
            genus = parent_of.get(species_taxid)
            if genus is not None:
                by_genus.setdefault(genus, []).append(path)

        edges = normalize(self._genus_edges(by_genus))
        coverage = Coverage(rank=rank, measured=frozenset(by_genus))
        manifest = LayerManifest(
            layer_id=self.layer_id,
            layer_version=_version(universe.version, self._params(), edges, by_genus),
            rank=rank,
            directed=False,
            determinism="exact",
            source_pins=dict(sources.pins),
            params=self._params(),
        )
        return BuiltLayer(manifest=manifest, edges=edges, coverage=coverage)

    def _genus_edges(self, by_genus: dict[int, list[Any]]) -> list[Edge]:
        """Aggregate species patristic distances into genus–genus proximity edges."""
        genera = sorted(by_genus)
        raw: list[tuple[int, int, float]] = []
        for g1, g2 in combinations(genera, 2):
            distances = [cophenetic(p1, p2) for p1 in by_genus[g1] for p2 in by_genus[g2]]
            aggregated = fmean(distances) if self._aggregation == "mean" else min(distances)
            raw.append((g1, g2, aggregated))
        if not raw:
            return []
        max_distance = max(d for _, _, d in raw) or 1.0
        edges: list[Edge] = []
        for g1, g2, distance in raw:
            proximity = 1.0 - distance / max_distance
            if proximity >= self._threshold:
                edges.append((g1, g2, proximity))
        return edges

    def _params(self) -> dict[str, str]:
        return {"aggregation": self._aggregation, "threshold": repr(self._threshold)}


def _version(
    universe_version: str,
    params: dict[str, str],
    edges: list[Edge],
    by_genus: dict[int, list[Any]],
) -> str:
    """Content digest of the built layer — reproducibility key (doc 10 A.6 ``layer_version``)."""
    payload = {
        "universe": universe_version,
        "layer_id": PhylogenyLayer.layer_id,
        "params": params,
        "measured": sorted(by_genus),
        "edges": sorted((a, b, round(w, 12)) for a, b, w in edges),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
