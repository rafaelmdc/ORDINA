"""Taxon — the organism node, at genus or species rank (doc 10 A.3, decision B1 dual-rank)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Rank = Literal["genus", "species"]


class Taxon(BaseModel):
    """A single organism node in the universe.

    ``parent_genus`` is the genus taxid for a species row, and ``None`` for a genus row.
    It is what lets a species roll up to its genus for genus-primary analysis (B1).
    """

    taxid: int
    rank: Rank
    name: str
    parent_genus: int | None = None
