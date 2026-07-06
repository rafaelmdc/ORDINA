"""Concrete TaxonomyResolver implementations (doc 10 A.3, Slice 0).

``LocalTaxonomyResolver`` reads a small local NCBI dump (a TSV of nodes) and satisfies the
``ordina_core.TaxonomyResolver`` protocol. It is what Slice 0 runs on. The Braidworks-backed
resolver (over the ncbi weaver's ``taxonomy_resolver``) plugs into the same protocol in the next
wiring step, without any change to ``build_universe``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ordina_core import Taxon


class LocalTaxonomyResolver:
    """Resolve taxids from an in-memory table loaded from a local NCBI dump.

    Expected TSV columns: ``taxid``, ``rank``, ``name``, ``parent_genus`` (parent_genus blank for
    genus rows). Only genus/species rows are kept — other ranks resolve to ``None``.
    """

    def __init__(self, table: dict[int, Taxon]) -> None:
        self._table = table

    @classmethod
    def from_tsv(cls, path: str | Path) -> LocalTaxonomyResolver:
        table: dict[int, Taxon] = {}
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                rank = row["rank"].strip()
                if rank not in ("genus", "species"):
                    continue
                parent = (row.get("parent_genus") or "").strip()
                taxid = int(row["taxid"])
                table[taxid] = Taxon(
                    taxid=taxid,
                    rank=rank,
                    name=row["name"].strip(),
                    parent_genus=int(parent) if parent else None,
                )
        return cls(table)

    def resolve(self, taxid: int) -> Taxon | None:
        return self._table.get(taxid)
