"""Assembly of built layers into a sparse Multiplex + its supra-adjacency."""

from __future__ import annotations

import numpy as np
import pytest
from braidworks.core import BraidRegistry
from gtdb_weaver.factory import build_gtdb_weaver_fixture
from ordina_core import BuiltLayer, Coverage, LayerManifest, NodeUniverse, SourcePins, Taxon
from ordina_retes.layers import PhylogenyLayer
from ordina_retes.multiplex import assemble

_SPECIES = {562: 561, 1905676: 1905675, 41978: 1263, 3048838: 3048837, 2053517: 2053516}
_GENERA = sorted(set(_SPECIES.values()))


def _universe() -> NodeUniverse:
    nodes = [
        Taxon(taxid=s, rank="species", name=f"sp{s}", parent_genus=g) for s, g in _SPECIES.items()
    ]
    nodes += [Taxon(taxid=g, rank="genus", name=f"g{g}") for g in _GENERA]
    return NodeUniverse(version="v", disbiome_snapshot="fix", ncbi_version="fix", nodes=nodes)


def _phylogeny(u: NodeUniverse) -> BuiltLayer:
    reg = BraidRegistry()
    reg.register(build_gtdb_weaver_fixture())
    return PhylogenyLayer(registry=reg).build(u, SourcePins(pins={"gtdb": "fixture"}))


def _synthetic(u: NodeUniverse) -> BuiltLayer:
    return BuiltLayer(
        manifest=LayerManifest(layer_id="synthetic", layer_version="s1", rank="genus"),
        edges=[(_GENERA[0], _GENERA[1], 0.9)],
        coverage=Coverage(rank="genus", measured=frozenset(_GENERA[:2])),
    )


def test_assembled_matrix_is_square_and_ordered():
    u = _universe()
    m = assemble(u, [_phylogeny(u)])
    assert m.order == _GENERA
    A = m.layers["phylogeny.gtdb"]
    assert A.shape == (5, 5)


def test_undirected_layer_is_symmetric():
    u = _universe()
    A = assemble(u, [_phylogeny(u)]).layers["phylogeny.gtdb"].toarray()
    assert np.allclose(A, A.T)
    assert np.all(np.diag(A) == 0.0)  # no self-loops


def test_single_layer_supra_is_the_layer_itself():
    u = _universe()
    m = assemble(u, [_phylogeny(u)])
    supra = m.supra_adjacency(coupling=0.5).toarray()
    assert np.allclose(supra, m.layers["phylogeny.gtdb"].toarray())


def test_two_layer_supra_has_coupling_off_diagonal():
    u = _universe()
    m = assemble(u, [_phylogeny(u), _synthetic(u)])
    supra = m.supra_adjacency(coupling=0.25).toarray()
    assert supra.shape == (10, 10)
    # Off-diagonal block is coupling * identity: node i in layer 0 <-> node i in layer 1.
    assert supra[0, 5] == pytest.approx(0.25)
    assert supra[2, 7] == pytest.approx(0.25)
    assert supra[0, 6] == pytest.approx(0.0)
    # Diagonal blocks are the two layers.
    assert np.allclose(supra[:5, :5], m.layers["phylogeny.gtdb"].toarray())
    assert np.allclose(supra[5:, 5:], m.layers["synthetic"].toarray())


def test_rank_mismatch_is_rejected():
    u = _universe()
    species_layer = BuiltLayer(
        manifest=LayerManifest(layer_id="x", layer_version="v", rank="species"),
        coverage=Coverage(rank="species"),
    )
    with pytest.raises(ValueError, match="cannot assemble"):
        assemble(u, [species_layer], rank="genus")
