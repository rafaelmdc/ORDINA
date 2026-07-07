"""The ``ordina`` command (Typer) — doc 10 A.2 / A.5.

Two subcommands: ``build-universe`` (Slice 0) builds the hashed union ``NodeUniverse`` from a
file; ``recovery`` (Slice 1) builds the requested layers, assembles the multiplex, and runs the
recovery harness to a ``recovery_report.json`` — the end-to-end artifact of the go/no-go metric.
"""

from __future__ import annotations

import csv
from pathlib import Path

import typer
from braidworks.core import BraidRegistry
from ordina_core import Association, SourcePins, build_universe

from .layers import PhylogenyLayer
from .multiplex import assemble
from .recovery import grouped_kfold, partners_by_disease, run_recovery
from .taxonomy import LocalTaxonomyResolver

app = typer.Typer(add_completion=False, help="ORDINA Retes command line.")


@app.callback()
def _main() -> None:
    """A no-op callback that keeps Typer in multi-command mode, so subcommands keep their explicit
    names (e.g. ``ordina build-universe``) even while there is only one of them."""


def _read_associations(path: Path) -> list[Association]:
    """Read associations from a TSV.

    Columns: disease_meddra, taxid, direction, source, evidence_ref (+ optional disease_mondo).
    """
    out: list[Association] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            out.append(
                Association(
                    disease_meddra=row["disease_meddra"].strip(),
                    taxid=int(row["taxid"]),
                    direction=row["direction"].strip(),
                    source=row["source"].strip(),
                    evidence_ref=row["evidence_ref"].strip(),
                    disease_mondo=(row.get("disease_mondo") or "").strip() or None,
                )
            )
    return out


@app.command("build-universe")
def build_universe_cmd(
    associations: Path = typer.Option(
        ..., "--associations", "-a", exists=True, help="TSV of disease–organism associations."
    ),
    taxonomy: Path = typer.Option(
        ..., "--taxonomy", "-t", exists=True, help="TSV NCBI dump (taxid, rank, name, parent)."
    ),
    out: Path = typer.Option(Path("universe.json"), "--out", "-o", help="Output path."),
    disbiome_snapshot: str = typer.Option("dev", help="Disbiome snapshot id (repro pin)."),
    ncbi_version: str = typer.Option("dev", help="NCBI taxonomy version (repro pin)."),
) -> None:
    """Build the hashed union NodeUniverse and write it to JSON."""
    assocs = _read_associations(associations)
    tax = LocalTaxonomyResolver.from_tsv(taxonomy)
    universe = build_universe(
        assocs, tax, disbiome_snapshot=disbiome_snapshot, ncbi_version=ncbi_version
    )
    out.write_text(universe.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(
        f"Wrote {out} — version {universe.version[:12]}… "
        f"({len(universe.genus())} genus, {len(universe.species())} species)"
    )


def _gtdb_registry(
    *, fixture: bool, db_path: Path | None, tree_paths: list[Path], auto_setup: bool
) -> BraidRegistry:
    """A Braidworks registry with a GTDB weaver the phylogeny layer can fetch through."""
    registry = BraidRegistry()
    if fixture:
        from gtdb_weaver.factory import build_gtdb_weaver_fixture

        registry.register(build_gtdb_weaver_fixture())
    else:
        from gtdb_weaver.factory import build_gtdb_weaver

        registry.register(
            build_gtdb_weaver(
                db_path=str(db_path) if db_path else None,
                tree_paths=[str(p) for p in tree_paths] or None,
                auto_setup=auto_setup,
                enable_tree_placement=auto_setup or bool(tree_paths),
            )
        )
    return registry


@app.command("recovery")
def recovery_cmd(
    associations: Path = typer.Option(
        ..., "--associations", "-a", exists=True, help="TSV of disease–organism associations."
    ),
    taxonomy: Path = typer.Option(
        ..., "--taxonomy", "-t", exists=True, help="TSV NCBI dump (taxid, rank, name, parent)."
    ),
    layers: list[str] = typer.Option(
        ["phylogeny.gtdb"], "--layers", "-l", help="Layer ids to build and walk."
    ),
    out: Path = typer.Option(Path("recovery_report.json"), "--out", "-o", help="Output path."),
    k: int = typer.Option(5, help="Number of recovery folds."),
    seed: int = typer.Option(0, help="RNG seed (splits, bootstrap, permutation)."),
    disbiome_snapshot: str = typer.Option("dev", help="Disbiome snapshot id (repro pin)."),
    ncbi_version: str = typer.Option("dev", help="NCBI taxonomy version (repro pin)."),
    gtdb_pin: str = typer.Option("dev", help="GTDB release pin recorded on the layer."),
    fixture: bool = typer.Option(
        False, "--fixture", help="Use the bundled offline GTDB fixture (no download)."
    ),
    gtdb_db: Path | None = typer.Option(None, help="GTDB crosswalk SQLite (real run)."),
    gtdb_tree: list[Path] = typer.Option([], help="GTDB reference tree(s) (real run)."),
    gtdb_auto_setup: bool = typer.Option(False, help="Download GTDB data if absent."),
) -> None:
    """Build layers, assemble the multiplex, and run the recovery harness to JSON."""
    assocs = _read_associations(associations)
    tax = LocalTaxonomyResolver.from_tsv(taxonomy)
    universe = build_universe(
        assocs, tax, disbiome_snapshot=disbiome_snapshot, ncbi_version=ncbi_version
    )

    registry = _gtdb_registry(
        fixture=fixture, db_path=gtdb_db, tree_paths=gtdb_tree, auto_setup=gtdb_auto_setup
    )
    sources = SourcePins(pins={"gtdb": gtdb_pin})
    # The factories this CLI knows how to configure (Slice 1: phylogeny only).
    available = {PhylogenyLayer.layer_id: PhylogenyLayer(registry=registry)}

    built = []
    for layer_id in layers:
        factory = available.get(layer_id)
        if factory is None:
            raise typer.BadParameter(f"unknown or unconfigured layer: {layer_id}")
        built.append(factory.build(universe, sources))

    multiplex = assemble(universe, built, rank="genus")
    partners = partners_by_disease(assocs, universe)
    splits = grouped_kfold(partners, k=k, seed=seed)
    report = run_recovery(multiplex, splits, seed=seed)

    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    verdict = "PASS" if report.passes() else "no lift over the phylogeny null"
    typer.echo(
        f"Wrote {out} — {report.n_cases} cases, "
        f"lift {report.lift_vs_phylogeny:+.4f} "
        f"(95% CI [{report.ci95[0]:+.4f}, {report.ci95[1]:+.4f}], p={report.permutation_p:.3f}) "
        f"— {verdict}"
    )


if __name__ == "__main__":
    app()
