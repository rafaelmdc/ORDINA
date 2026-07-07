"""Recovery harness end-to-end on the offline fixture, plus metric/split units."""

from __future__ import annotations

import pytest
from braidworks.core import BraidRegistry
from gtdb_weaver.factory import build_gtdb_weaver_fixture
from ordina_core import Association, NodeUniverse, SourcePins, Taxon
from ordina_retes.layers import PhylogenyLayer
from ordina_retes.multiplex import Multiplex, assemble
from ordina_retes.recovery import (
    auprc,
    grouped_kfold,
    partners_by_disease,
    predict,
    r_precision,
    recall_at_k,
    run_recovery,
    temporal_split,
)

_SPECIES = {562: 561, 1905676: 1905675, 41978: 1263, 3048838: 3048837, 2053517: 2053516}


def _universe() -> NodeUniverse:
    nodes = [
        Taxon(taxid=s, rank="species", name=f"sp{s}", parent_genus=g) for s, g in _SPECIES.items()
    ]
    nodes += [Taxon(taxid=g, rank="genus", name=f"g{g}") for g in sorted(set(_SPECIES.values()))]
    return NodeUniverse(version="v", disbiome_snapshot="fix", ncbi_version="fix", nodes=nodes)


def _multiplex(u: NodeUniverse) -> Multiplex:
    reg = BraidRegistry()
    reg.register(build_gtdb_weaver_fixture())
    layer = PhylogenyLayer(registry=reg).build(u, SourcePins(pins={"gtdb": "fixture"}))
    return assemble(u, [layer])


def _assoc(disease: str, taxid: int) -> Association:
    return Association(
        disease_meddra=disease,
        taxid=taxid,
        direction="enriched",
        source="test",
        evidence_ref="e",
    )


# --- metrics -----------------------------------------------------------------


def test_recall_at_k():
    assert recall_at_k([1, 2, 3, 4], {2, 9}, k=2) == pytest.approx(0.5)
    assert recall_at_k([1, 2, 3, 4], {2, 3}, k=4) == pytest.approx(1.0)


def test_r_precision_and_auprc_perfect_ranking():
    ranked, truth = [5, 6, 7, 8], {5, 6}
    assert r_precision(ranked, truth) == pytest.approx(1.0)
    assert auprc(ranked, truth) == pytest.approx(1.0)  # both positives at the top


def test_auprc_penalizes_late_hits():
    assert auprc([9, 8, 5], {5}) == pytest.approx(1 / 3)  # single truth found at rank 3


# --- split -------------------------------------------------------------------


def test_partners_roll_up_to_genus():
    u = _universe()
    partners = partners_by_disease([_assoc("D1", 562), _assoc("D1", 41978)], u)
    assert partners == {"D1": {561, 1263}}  # species 562->genus 561, 41978->1263


def test_grouped_kfold_seed_and_truth_are_disjoint():
    partners = {"D1": {561, 1263, 1905675, 3048837}}
    splits = grouped_kfold(partners, k=2, seed=1)
    for split in splits:
        for case in split.cases:
            assert set(case.seed).isdisjoint(case.truth)
            assert set(case.seed) | set(case.truth) == partners["D1"]


def test_temporal_split_recovers_only_new_links():
    split = temporal_split({"D1": {561}}, {"D1": {561, 1263}})
    assert split.cases[0].seed == (561,)
    assert split.cases[0].truth == (1263,)


# --- predict + harness -------------------------------------------------------


def test_predict_ranks_a_close_genus_above_a_far_one():
    u = _universe()
    m = _multiplex(u)
    ranked = dict(predict(m, [561]))  # seed Escherichia
    # Opacimonas (1905675) is its tree neighbour; JABGUH (2053516) is far.
    assert ranked[1905675] > ranked[2053516]


def test_run_recovery_produces_a_report():
    u = _universe()
    m = _multiplex(u)
    # Two diseases, each linking a close genus pair, so there is signal to recover.
    assocs = [
        _assoc("D1", 561),
        _assoc("D1", 1905675),
        _assoc("D2", 1263),
        _assoc("D2", 3048837),
    ]
    partners = partners_by_disease(assocs, u)
    splits = grouped_kfold(partners, k=2, seed=0)
    report = run_recovery(m, splits, recall_k=5, n_boot=200, n_perm=200, seed=0)

    assert report.n_cases > 0
    assert "predictor" in report.methods and "phylogeny" in report.methods
    assert 0.0 <= report.methods["predictor"].auprc <= 1.0
    # Slice 1 has only the phylogeny layer, so the predictor IS the phylogeny null: zero lift.
    assert report.lift_vs_phylogeny == pytest.approx(0.0)
    assert not report.passes()  # the gate needs the metabolic layer (Slice 2)


def test_recovery_report_serializes_to_json():
    u = _universe()
    m = _multiplex(u)
    partners = partners_by_disease([_assoc("D1", 561), _assoc("D1", 1905675)], u)
    report = run_recovery(m, grouped_kfold(partners, k=2), n_boot=50, n_perm=50)
    assert "lift_vs_phylogeny" in report.model_dump_json()
