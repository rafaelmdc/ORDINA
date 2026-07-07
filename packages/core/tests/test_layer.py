"""Tests for the framework-free layer contract."""

from __future__ import annotations

import pytest
from ordina_core import BuiltLayer, Coverage, LayerManifest, normalize


def test_normalize_maps_ranks_into_unit_interval():
    edges = [(1, 2, 10.0), (1, 3, 30.0), (2, 3, 20.0)]
    out = dict(((a, b), w) for a, b, w in normalize(edges))
    assert out[(1, 2)] == pytest.approx(0.0)  # smallest raw weight -> 0
    assert out[(2, 3)] == pytest.approx(0.5)  # middle -> 0.5
    assert out[(1, 3)] == pytest.approx(1.0)  # largest -> 1


def test_normalize_averages_ties():
    edges = [(1, 2, 5.0), (1, 3, 5.0), (2, 3, 9.0)]
    out = dict(((a, b), w) for a, b, w in normalize(edges))
    # The two tied smallest share average rank (0+1)/2 = 0.5, /2 -> 0.25.
    assert out[(1, 2)] == pytest.approx(0.25)
    assert out[(1, 3)] == pytest.approx(0.25)
    assert out[(2, 3)] == pytest.approx(1.0)


def test_normalize_preserves_edge_order_and_endpoints():
    edges = [(7, 8, 2.0), (8, 9, 1.0)]
    out = normalize(edges)
    assert [(a, b) for a, b, _ in out] == [(7, 8), (8, 9)]


def test_normalize_empty():
    assert normalize([]) == []


def test_coverage_state():
    cov = Coverage(rank="genus", measured=frozenset({1, 2}))
    assert cov.state(1) == "measured"
    assert cov.state(99) == "unmeasured"


def test_built_layer_roundtrips_through_json():
    layer = BuiltLayer(
        manifest=LayerManifest(layer_id="phylogeny.gtdb", layer_version="abc123", rank="genus"),
        edges=[(1, 2, 0.5)],
        coverage=Coverage(rank="genus", measured=frozenset({1, 2})),
    )
    restored = BuiltLayer.model_validate_json(layer.model_dump_json())
    assert restored.edges == [(1, 2, 0.5)]
    assert restored.coverage.state(2) == "measured"
    assert restored.manifest.layer_id == "phylogeny.gtdb"
