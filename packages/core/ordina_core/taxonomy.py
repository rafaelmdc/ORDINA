"""TaxonomyResolver — the seam between the framework-free core and a real NCBI backend.

``build_universe`` (universe.py) needs to turn a bare taxid into a ranked ``Taxon`` with its
parent genus. It does not care *how* — a local NCBI dump, the Braidworks ncbi weaver, or a test
fixture. Core defines the contract as a Protocol; the concrete resolver lives in ``ordina-retes``
so that ``ordina-core`` stays dependency-free.
"""

from __future__ import annotations

from typing import Protocol

from .taxon import Taxon


class TaxonomyResolver(Protocol):
    """Resolve an NCBI taxid to a ``Taxon`` (with rank + parent genus), or ``None`` if unknown."""

    def resolve(self, taxid: int) -> Taxon | None: ...
