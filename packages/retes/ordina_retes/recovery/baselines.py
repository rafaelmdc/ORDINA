"""Baselines & controls (doc 09 §5) — the shortcuts a real recovery must beat.

A good recovery number is worthless unless it beats the stupid shortcuts run through the
*same* hide-and-predict procedure: the **phylogeny null** (related organisms trivially look
alike), the **study-effort null** (well-studied organisms show up everywhere), the
**enrichment-coverage null** (nodes that merely carry a lot of biology), a degree/random
floor, and a **propagation-only control** (genus relatedness with biology stripped).
"""

from __future__ import annotations

import random

import numpy as np

from ..multiplex import Multiplex
from .predict import predict

PHYLOGENY_LAYER = "phylogeny.gtdb"


def _restrict(m: Multiplex, layer_ids: list[str]) -> Multiplex:
    keep = [lid for lid in layer_ids if lid in m.layers]
    return Multiplex(
        universe=m.universe,
        rank=m.rank,
        order=m.order,
        layers={lid: m.layers[lid] for lid in keep},
        coverage={lid: m.coverage[lid] for lid in keep if lid in m.coverage},
    )


def baseline_phylogeny(m: Multiplex, seed_taxa: list[int]) -> list[tuple[int, float]]:
    """The phylogeny null: the same RWR, but walking the GTDB phylogeny layer alone."""
    if PHYLOGENY_LAYER not in m.layers:
        return []
    return predict(_restrict(m, [PHYLOGENY_LAYER]), seed_taxa)


def control_propagation_only(m: Multiplex, seed_taxa: list[int]) -> list[tuple[int, float]]:
    """Propagation-only control (doc 09 §5): relatedness diffusion with biology stripped.

    With only the phylogeny layer present this coincides with the phylogeny null — it becomes
    distinct once enrichment layers exist, isolating "a genus-rollup win" from real biology.
    """
    return baseline_phylogeny(m, seed_taxa)


def baseline_degree_random(
    m: Multiplex, seed_taxa: list[int], *, seed: int = 0
) -> list[tuple[int, float]]:
    """Rank non-seed nodes by summed multiplex degree, random tie-break — the floor."""
    degree = np.zeros(m.n)
    for adjacency in m.layers.values():
        degree += np.asarray(adjacency.sum(axis=1)).ravel()
    rng = random.Random(seed)
    seed_set = set(seed_taxa)
    ranked = [(t, float(degree[i])) for i, t in enumerate(m.order) if t not in seed_set]
    rng.shuffle(ranked)  # randomize, then stable-sort so ties are random
    ranked.sort(key=lambda kv: -kv[1])
    return ranked


def baseline_study_effort(train_partners: dict[str, set[int]]) -> list[tuple[int, float]]:
    """Rank taxa by TRAINING studiedness only — how many diseases' kept links mention them.

    Uses the seed (training) side only, never the hidden truth, so it can't peek (doc 09 §5).
    """
    count: dict[int, float] = {}
    for partners in train_partners.values():
        for taxid in partners:
            count[taxid] = count.get(taxid, 0.0) + 1.0
    return sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))


def baseline_enrichment_coverage(m: Multiplex) -> list[tuple[int, float]]:
    """Rank taxa by how much biology they carry — the number of layers that measured them."""
    score: dict[int, float] = {t: 0.0 for t in m.order}
    for coverage in m.coverage.values():
        for taxid in coverage.measured:
            if taxid in score:
                score[taxid] += 1.0
    return sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
