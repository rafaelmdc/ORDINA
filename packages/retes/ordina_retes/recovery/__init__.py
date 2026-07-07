"""Recovery harness (doc 09) — hide known links, predict, score against the nulls."""

from __future__ import annotations

from .baselines import (
    baseline_degree_random,
    baseline_enrichment_coverage,
    baseline_phylogeny,
    baseline_study_effort,
    control_propagation_only,
)
from .harness import MethodScore, RecoveryReport, run_recovery
from .metrics import auprc, r_precision, recall_at_k
from .predict import predict
from .split import Case, Split, grouped_kfold, partners_by_disease, temporal_split

__all__ = [
    "Case",
    "MethodScore",
    "RecoveryReport",
    "Split",
    "auprc",
    "baseline_degree_random",
    "baseline_enrichment_coverage",
    "baseline_phylogeny",
    "baseline_study_effort",
    "control_propagation_only",
    "grouped_kfold",
    "partners_by_disease",
    "predict",
    "r_precision",
    "recall_at_k",
    "run_recovery",
    "temporal_split",
]
