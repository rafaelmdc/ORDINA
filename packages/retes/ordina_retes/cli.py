"""The ``ordina`` command (Typer) — doc 10 A.2 / A.5.

Slice 0 ships one subcommand: ``build-universe``. It reads disease–organism associations and a
local taxonomy dump, builds the hashed union ``NodeUniverse`` (decision B5), and writes it to JSON.
"""

from __future__ import annotations

import csv
from pathlib import Path

import typer
from ordina_core import Association, build_universe

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


if __name__ == "__main__":
    app()
