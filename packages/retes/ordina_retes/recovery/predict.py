"""predict — random walk with restart over the multiplex (doc 10 A.5, doc 09 §2).

Seeds are a disease's *kept* partner organisms; the walk diffuses from them across the
multiplex (all layers, coupled) and ranks every other node by stationary visit probability.
The predictor is enrichment-only and disease-independent — only the seed set changes per
fold — so no per-fold rebuild is needed (doc 09 §2).
"""

from __future__ import annotations

import numpy as np
from scipy import sparse

from ..multiplex import Multiplex


def predict(
    m: Multiplex,
    seed_taxa: list[int],
    *,
    restart: float = 0.7,
    coupling: float = 0.5,
    tol: float = 1e-10,
    max_iter: int = 500,
) -> list[tuple[int, float]]:
    """Rank non-seed nodes by RWR score from ``seed_taxa``. Empty if nothing seeds.

    The supra-adjacency is column-normalized to a transition matrix; the walk restarts to
    the seed (spread over every layer copy) with probability ``restart``. Node scores sum a
    node's mass across layers. Returns ``(taxid, score)`` best-first, ties broken by taxid.
    """
    order = m.order
    n = len(order)
    position = {taxid: i for i, taxid in enumerate(order)}
    seed_idx = [position[t] for t in seed_taxa if t in position]
    if n == 0 or not seed_idx:
        return []

    supra = m.supra_adjacency(coupling).astype(float)
    layers = supra.shape[0] // n
    column_sums = np.asarray(supra.sum(axis=0)).ravel()
    inverse = np.divide(1.0, column_sums, out=np.zeros_like(column_sums), where=column_sums > 0)
    transition = supra @ sparse.diags(inverse)

    restart_vec = np.zeros(n * layers)
    for i in seed_idx:
        for layer in range(layers):
            restart_vec[layer * n + i] = 1.0
    restart_vec /= restart_vec.sum()

    x = restart_vec.copy()
    for _ in range(max_iter):
        nxt = (1.0 - restart) * (transition @ x) + restart * restart_vec
        if np.abs(nxt - x).sum() < tol:
            x = nxt
            break
        x = nxt

    score = np.zeros(n)
    for layer in range(layers):
        score += x[layer * n : (layer + 1) * n]

    seed_set = set(seed_idx)
    return sorted(
        ((order[i], float(score[i])) for i in range(n) if i not in seed_set),
        key=lambda kv: (-kv[1], kv[0]),
    )
