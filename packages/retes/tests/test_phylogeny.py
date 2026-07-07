"""PhylogenyLayer built against the offline gtdb_weaver fixture (injected registry)."""

from __future__ import annotations

import pytest
from braidworks.core import BraidRegistry
from gtdb_weaver.factory import build_gtdb_weaver_fixture
from ordina_core import NodeUniverse, SourcePins, Taxon
from ordina_retes.layers import PhylogenyLayer

# Fixture species (ncbi taxid -> its invented parent-genus taxid). Each is its own genus, so
# the 5 genera give C(5,2)=10 edges. Distances come from data/fixture_tree.nwk.
_ESCHERICHIA, _OPACIMONAS, _RUMINOCOCCUS, _AVISPIRILLUM, _JABGUH = (
    561,
    1905675,
    1263,
    3048837,
    2053516,
)
_SPECIES = {
    562: _ESCHERICHIA,
    1905676: _OPACIMONAS,
    41978: _RUMINOCOCCUS,
    3048838: _AVISPIRILLUM,
    2053517: _JABGUH,
}


def _universe(extra_species: dict[int, int] | None = None) -> NodeUniverse:
    species = dict(_SPECIES)
    if extra_species:
        species.update(extra_species)
    nodes: list[Taxon] = []
    for sp, genus in species.items():
        nodes.append(Taxon(taxid=sp, rank="species", name=f"sp{sp}", parent_genus=genus))
    for genus in sorted(set(species.values())):
        nodes.append(Taxon(taxid=genus, rank="genus", name=f"g{genus}"))
    return NodeUniverse(version="v-test", disbiome_snapshot="fix", ncbi_version="fix", nodes=nodes)


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(build_gtdb_weaver_fixture())
    return reg


def _build(**kwargs):
    return PhylogenyLayer(registry=_registry(), **kwargs).build(
        _universe(), SourcePins(pins={"gtdb": "fixture"})
    )


def test_builds_complete_genus_graph():
    layer = _build()
    assert layer.manifest.rank == "genus"
    assert layer.coverage.measured == frozenset(_SPECIES.values())
    assert len(layer.edges) == 10  # C(5,2)


def test_weights_are_in_unit_interval():
    layer = _build()
    assert all(0.0 <= w <= 1.0 for _, _, w in layer.edges)


def test_closest_genera_get_the_top_weight():
    layer = _build()
    weight = {frozenset((a, b)): w for a, b, w in layer.edges}
    # Ruminococcus & Avispirillum are the closest pair on the fixture tree (dist 0.625) ...
    assert weight[frozenset((_RUMINOCOCCUS, _AVISPIRILLUM))] == pytest.approx(1.0)
    # ... and Opacimonas & Avispirillum the farthest (dist 1.875).
    assert weight[frozenset((_OPACIMONAS, _AVISPIRILLUM))] == pytest.approx(0.0)


def test_unplaced_species_leaves_its_genus_unmeasured():
    # A species whose taxid is not in the fixture crosswalk cannot be placed.
    layer = PhylogenyLayer(registry=_registry()).build(
        _universe(extra_species={999999: 888888}), SourcePins(pins={"gtdb": "fixture"})
    )
    assert 888888 not in layer.coverage.measured
    assert layer.coverage.state(888888) == "unmeasured"


def test_build_is_deterministic():
    a, b = _build(), _build()
    assert a.manifest.layer_version == b.manifest.layer_version
    assert a.edges == b.edges
