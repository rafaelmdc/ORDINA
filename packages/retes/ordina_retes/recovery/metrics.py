"""Recovery metrics (doc 09 §5) — how well a ranked prediction recovers hidden truth.

Each takes a ``ranked`` list of candidate taxids (best first, seeds already removed) and the
``truth`` set of hidden partner taxids to recover. All return a float in [0, 1].
"""

from __future__ import annotations

from collections.abc import Sequence


def recall_at_k(ranked: Sequence[int], truth: set[int], k: int) -> float:
    """Fraction of the hidden truth found in the top ``k`` predictions."""
    if not truth:
        return 0.0
    top = set(ranked[:k])
    return len(top & truth) / len(truth)


def r_precision(ranked: Sequence[int], truth: set[int]) -> float:
    """Precision at ``k = |truth|`` — a per-disease-fair cutoff (doc 09 §5)."""
    if not truth:
        return 0.0
    k = len(truth)
    top = set(ranked[:k])
    return len(top & truth) / k


def auprc(ranked: Sequence[int], truth: set[int]) -> float:
    """Average precision over the ranking — the area under the precision–recall curve.

    Precision is averaged at each rank where a true positive is recovered; unranked truth
    contributes 0. Equivalent to AP, the standard AUPRC estimator for a ranked list.
    """
    if not truth:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for i, taxid in enumerate(ranked, start=1):
        if taxid in truth:
            hits += 1
            precision_sum += hits / i
    return precision_sum / len(truth)
