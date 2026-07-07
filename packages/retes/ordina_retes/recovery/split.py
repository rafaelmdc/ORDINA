"""Train/test splits for recovery (doc 09 §2–3).

A :class:`Case` is one disease's hide-and-predict instance: ``seed`` = its kept partner
organisms (what the walk starts from), ``truth`` = its hidden partners (what we score
recovery against). A :class:`Split` is a fold's worth of cases.

The honest-split guards of doc 09 (look-alike diseases grouped so a near-duplicate can't
leak its answer, A4) are threaded through ``disease_groups`` — kept together within a fold.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from ordina_core import Association, NodeUniverse, Rank


@dataclass(frozen=True)
class Case:
    disease: str
    seed: tuple[int, ...]  # kept partner taxids (the walk's seeds)
    truth: tuple[int, ...]  # hidden partner taxids (recovery target)


@dataclass
class Split:
    name: str
    cases: list[Case]


def partners_by_disease(
    assocs: Iterable[Association], universe: NodeUniverse, rank: Rank = "genus"
) -> dict[str, set[int]]:
    """Disease MedDRA code -> its partner taxids rolled up to ``rank`` (genus is primary, B1).

    A species association rolls up to its parent genus; a genus association stays. Taxids not
    in the universe at that rank are dropped.
    """
    if rank != "genus":
        raise NotImplementedError("only genus-rank rollup is implemented (B1 primary)")
    rollup: dict[int, int] = {}
    for taxon in universe.nodes:
        if taxon.rank == "genus":
            rollup[taxon.taxid] = taxon.taxid
        elif taxon.parent_genus is not None:
            rollup[taxon.taxid] = taxon.parent_genus
    partners: dict[str, set[int]] = {}
    for a in assocs:
        genus = rollup.get(a.taxid)
        if genus is not None:
            partners.setdefault(a.disease_meddra, set()).add(genus)
    return partners


def _fold_partition(items: list[int], k: int, rng: random.Random) -> list[list[int]]:
    shuffled = sorted(items)
    rng.shuffle(shuffled)
    return [sorted(shuffled[i::k]) for i in range(k)]


def grouped_kfold(
    partners: dict[str, set[int]],
    k: int = 5,
    *,
    seed: int = 0,
    disease_groups: dict[str, str] | None = None,
) -> list[Split]:
    """k folds hiding a different 1/k of each disease's partners as truth (doc 09 §2).

    Each disease's partners are partitioned into k parts (deterministic given ``seed``);
    fold ``f`` hides part ``f`` (truth) and seeds from the rest. A disease contributes a case
    to a fold only when both its seed and truth are non-empty, so diseases with a single
    partner are skipped. ``disease_groups`` is accepted for the look-alike-grouping guard
    (A4); the shared-organism-overlap grouping that consumes it lands with Slice 2.
    """
    rng = random.Random(seed)
    folds_by_disease = {
        disease: _fold_partition(sorted(ps), k, rng) for disease, ps in sorted(partners.items())
    }
    splits: list[Split] = []
    for f in range(k):
        cases: list[Case] = []
        for disease, folds in folds_by_disease.items():
            truth = folds[f]
            kept = [t for i, fold in enumerate(folds) if i != f for t in fold]
            if truth and kept:
                cases.append(Case(disease, tuple(sorted(kept)), tuple(sorted(truth))))
        splits.append(Split(name=f"fold{f}", cases=cases))
    return splits


def temporal_split(old: dict[str, set[int]], new: dict[str, set[int]]) -> Split:
    """Seed on an older snapshot, recover the links that appeared later (doc 09 §3).

    For each disease, ``seed`` = its partners in ``old``, ``truth`` = partners present in
    ``new`` but not ``old``. The harder, more honest split — it mimics predicting the future.
    """
    cases: list[Case] = []
    for disease, new_partners in sorted(new.items()):
        old_partners = old.get(disease, set())
        truth = new_partners - old_partners
        if truth and old_partners:
            cases.append(Case(disease, tuple(sorted(old_partners)), tuple(sorted(truth))))
    return Split("temporal", cases)
