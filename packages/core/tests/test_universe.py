"""Tests for the framework-free core: node universe construction + determinism."""

from __future__ import annotations

import importlib
import pkgutil
import sys

from ordina_core import Association, NodeUniverse, Taxon, build_universe, compute_version


class _FakeResolver:
    """A TaxonomyResolver over an in-memory table (satisfies the core Protocol)."""

    def __init__(self, table: dict[int, Taxon]) -> None:
        self._table = table

    def resolve(self, taxid: int) -> Taxon | None:
        return self._table.get(taxid)


def _resolver() -> _FakeResolver:
    return _FakeResolver(
        {
            816: Taxon(taxid=816, rank="genus", name="Bacteroides"),
            818: Taxon(
                taxid=818, rank="species", name="Bacteroides thetaiotaomicron", parent_genus=816
            ),
            1350: Taxon(taxid=1350, rank="genus", name="Enterococcus"),
        }
    )


def _assocs() -> list[Association]:
    return [
        Association(
            disease_meddra="10011401",
            taxid=818,
            direction="enriched",
            source="disbiome",
            evidence_ref="e1",
        ),
        Association(
            disease_meddra="10011401",
            taxid=1350,
            direction="depleted",
            source="disbiome",
            evidence_ref="e2",
        ),
    ]


def test_species_pulls_in_parent_genus() -> None:
    u = build_universe(_assocs(), _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    taxids = {t.taxid for t in u.nodes}
    # 818 (species) + its parent 816 (genus) + 1350 (genus)
    assert taxids == {816, 818, 1350}
    assert {t.taxid for t in u.genus()} == {816, 1350}
    assert {t.taxid for t in u.species()} == {818}


def test_version_is_deterministic_and_order_independent() -> None:
    u1 = build_universe(_assocs(), _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    u2 = build_universe(
        list(reversed(_assocs())), _resolver(), disbiome_snapshot="s1", ncbi_version="n1"
    )
    assert u1.version == u2.version


def test_version_changes_with_source_pins() -> None:
    u1 = build_universe(_assocs(), _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    u2 = build_universe(_assocs(), _resolver(), disbiome_snapshot="s2", ncbi_version="n1")
    assert u1.version != u2.version


def test_index_is_per_rank_and_taxid_ordered() -> None:
    u = build_universe(_assocs(), _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    assert u.index("genus") == {816: 0, 1350: 1}
    assert u.index("species") == {818: 0}


def test_unresolvable_taxid_is_skipped() -> None:
    assocs = _assocs() + [
        Association(
            disease_meddra="x",
            taxid=999999,
            direction="enriched",
            source="disbiome",
            evidence_ref="e3",
        )
    ]
    u = build_universe(assocs, _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    assert 999999 not in {t.taxid for t in u.nodes}


def test_compute_version_matches_roundtrip() -> None:
    u = build_universe(_assocs(), _resolver(), disbiome_snapshot="s1", ncbi_version="n1")
    assert u.version == compute_version(u.nodes, "s1", "n1")
    # A serialized universe reloads identically.
    assert NodeUniverse.model_validate_json(u.model_dump_json()).version == u.version


def test_core_imports_no_django() -> None:
    """Boundary rule A.1/A.9: ordina-core must not pull in Django (directly or transitively)."""
    import ordina_core

    for mod in pkgutil.walk_packages(ordina_core.__path__, prefix="ordina_core."):
        importlib.import_module(mod.name)
    assert not any(name == "django" or name.startswith("django.") for name in sys.modules)
