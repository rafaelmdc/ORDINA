"""run_recovery — the harness that turns splits into a scored report (doc 09 §5, §10).

For every case it runs the predictor and each baseline through the identical hide-and-predict
procedure, scores recovery of the hidden truth, and asks the one question the gate rests on:
does the predictor beat the **phylogeny null**? That comparison is *paired* per case, with a
bootstrap CI on the mean lift and a sign-flip permutation p-value (doc 09 §10, the A2 decision).

With only the phylogeny layer present the predictor *is* the phylogeny walk, so the expected
Slice-1 result is zero lift — the harness runs end to end and honestly reports "no lift yet".
The lift appears in Slice 2 when the metabolic layer joins the walk.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from pydantic import BaseModel

from ..multiplex import Multiplex
from .baselines import (
    baseline_degree_random,
    baseline_enrichment_coverage,
    baseline_phylogeny,
    baseline_study_effort,
    control_propagation_only,
)
from .metrics import auprc, r_precision, recall_at_k
from .predict import predict
from .split import Split

PRIMARY = "predictor"
NULL = "phylogeny"


class MethodScore(BaseModel):
    method: str
    auprc: float
    r_precision: float
    recall_at_k: float


class RecoveryReport(BaseModel):
    """The recovery outcome — per-method means plus the predictor-vs-null verdict."""

    n_cases: int
    recall_k: int
    primary_metric: str
    methods: dict[str, MethodScore]
    lift_vs_phylogeny: float  # mean per-case (predictor − phylogeny) on the primary metric
    ci95: tuple[float, float]  # paired bootstrap CI of the lift
    permutation_p: float

    def passes(self) -> bool:
        """A2 gate (doc 09 §10): predictor beats the phylogeny null — CI above 0 and significant."""
        return self.ci95[0] > 0.0 and self.permutation_p < 0.05


def _ranked_taxids(pairs: list[tuple[int, float]], seed_set: set[int]) -> list[int]:
    return [t for t, _ in pairs if t not in seed_set]


def run_recovery(
    m: Multiplex,
    splits: list[Split],
    *,
    recall_k: int = 10,
    n_boot: int = 2000,
    n_perm: int = 2000,
    seed: int = 0,
) -> RecoveryReport:
    """Score the predictor and baselines over all cases; return the recovery report."""
    # Per-method, per-case primary-metric (AUPRC) values, plus the secondary metrics.
    scores: dict[str, dict[str, list[float]]] = {}

    def record(method: str, ranked: list[int], truth: set[int]) -> None:
        bucket = scores.setdefault(method, {"auprc": [], "r_precision": [], "recall_at_k": []})
        bucket["auprc"].append(auprc(ranked, truth))
        bucket["r_precision"].append(r_precision(ranked, truth))
        bucket["recall_at_k"].append(recall_at_k(ranked, truth, recall_k))

    for split in splits:
        # Training studiedness for this fold = the kept (seed) side only (no peeking).
        train_partners = {c.disease: set(c.seed) for c in split.cases}
        study = baseline_study_effort(train_partners)
        coverage_rank = baseline_enrichment_coverage(m)

        # Seed-independent baselines: one ranking per fold, seeds stripped per case.
        globals_: dict[str, list[tuple[int, float]]] = {
            "study_effort": study,
            "enrichment_coverage": coverage_rank,
        }
        # Seed-dependent methods, evaluated per case.
        per_case: dict[str, Callable[[list[int]], list[tuple[int, float]]]] = {
            PRIMARY: lambda s: predict(m, s),
            NULL: lambda s: baseline_phylogeny(m, s),
            "propagation_only": lambda s: control_propagation_only(m, s),
            "degree_random": lambda s: baseline_degree_random(m, s, seed=seed),
        }

        for case in split.cases:
            seed_set = set(case.seed)
            truth = set(case.truth)
            for method, fn in per_case.items():
                record(method, _ranked_taxids(fn(list(case.seed)), seed_set), truth)
            for method, ranking in globals_.items():
                record(method, _ranked_taxids(ranking, seed_set), truth)

    n_cases = len(scores.get(PRIMARY, {}).get("auprc", []))
    if n_cases == 0:
        return RecoveryReport(
            n_cases=0,
            recall_k=recall_k,
            primary_metric="auprc",
            methods={},
            lift_vs_phylogeny=0.0,
            ci95=(0.0, 0.0),
            permutation_p=1.0,
        )

    methods = {
        name: MethodScore(
            method=name,
            auprc=float(np.mean(vals["auprc"])),
            r_precision=float(np.mean(vals["r_precision"])),
            recall_at_k=float(np.mean(vals["recall_at_k"])),
        )
        for name, vals in scores.items()
    }

    predictor = np.array(scores[PRIMARY]["auprc"])
    null = np.array(scores[NULL]["auprc"])
    diffs = predictor - null
    observed = float(diffs.mean())

    rng = np.random.default_rng(seed)
    boot = np.array(
        [rng.choice(diffs, size=diffs.size, replace=True).mean() for _ in range(n_boot)]
    )
    ci95 = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))

    signs = rng.choice([-1.0, 1.0], size=(n_perm, diffs.size))
    null_means = (signs * np.abs(diffs)).mean(axis=1)
    permutation_p = float((np.sum(null_means >= observed) + 1) / (n_perm + 1))

    return RecoveryReport(
        n_cases=n_cases,
        recall_k=recall_k,
        primary_metric="auprc",
        methods=methods,
        lift_vs_phylogeny=observed,
        ci95=ci95,
        permutation_p=permutation_p,
    )
