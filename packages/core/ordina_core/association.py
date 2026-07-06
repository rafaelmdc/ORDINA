"""Association — the flattened disease–organism evidence row (doc 10 A.3, A.6).

This is a *projection* of Mind's normalized ``QualitativeFinding`` (doc 01), NOT a second
source of truth. One row per disease–taxon–direction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Direction = Literal["enriched", "depleted"]


class Association(BaseModel):
    """A disease-to-organism association projected from Mind.

    ``direction`` is projected from Mind's ``QualitativeFinding.Direction``:
    ``enriched|increased|elevated -> "enriched"``; ``depleted|decreased|reduced -> "depleted"``.
    Mind has no "unchanged" state.
    """

    disease_meddra: str  # working key in iteration 1 (Disbiome-only), decision D1
    taxid: int
    direction: Direction
    source: str  # "disbiome", "gmrepo", …
    evidence_ref: str
    disease_mondo: str | None = None  # nullable; filled from the confirmed crosswalk
