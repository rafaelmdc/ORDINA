"""End-to-end test of `ordina build-universe` (Slice 0 done-criterion)."""

from __future__ import annotations

import json
from pathlib import Path

from ordina_core import NodeUniverse
from ordina_retes.cli import app
from ordina_retes.taxonomy import LocalTaxonomyResolver
from typer.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_local_resolver_skips_non_genus_species_ranks() -> None:
    tax = LocalTaxonomyResolver.from_tsv(FIXTURES / "taxonomy.tsv")
    assert tax.resolve(818) is not None
    assert tax.resolve(543) is None  # family rank -> not kept


def test_build_universe_end_to_end(tmp_path: Path) -> None:
    out = tmp_path / "universe.json"
    result = runner.invoke(
        app,
        [
            "build-universe",
            "-a", str(FIXTURES / "associations.tsv"),
            "-t", str(FIXTURES / "taxonomy.tsv"),
            "-o", str(out),
            "--disbiome-snapshot", "s1",
            "--ncbi-version", "n1",
        ],
    )
    assert result.exit_code == 0, result.output
    u = NodeUniverse.model_validate_json(out.read_text())
    # 816, 818 (+parent 816), 1350 -> genus {816, 1350}, species {818}
    assert {t.taxid for t in u.genus()} == {816, 1350}
    assert {t.taxid for t in u.species()} == {818}
    assert len(u.version) == 64  # sha256 hex
    # JSON is valid and carries the reproducibility pins.
    payload = json.loads(out.read_text())
    assert payload["disbiome_snapshot"] == "s1"
    assert payload["ncbi_version"] == "n1"


def test_build_universe_is_reproducible(tmp_path: Path) -> None:
    args = lambda p: [  # noqa: E731
        "build-universe",
        "-a", str(FIXTURES / "associations.tsv"),
        "-t", str(FIXTURES / "taxonomy.tsv"),
        "-o", str(p),
    ]
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert runner.invoke(app, args(a)).exit_code == 0
    assert runner.invoke(app, args(b)).exit_code == 0
    va = NodeUniverse.model_validate_json(a.read_text()).version
    vb = NodeUniverse.model_validate_json(b.read_text()).version
    assert va == vb
