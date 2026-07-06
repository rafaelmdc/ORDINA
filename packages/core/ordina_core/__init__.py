"""ordina-core — the domain types every ORDINA module shares.

Framework-free by contract: this package imports no Django and no web framework, so the CLI,
the offline pipeline, the workers, and the web API can all import the same objects (doc 10 A.1).
"""

from __future__ import annotations

from .association import Association, Direction
from .sources import Source, SourcePins
from .taxon import Rank, Taxon
from .taxonomy import TaxonomyResolver
from .universe import NodeUniverse, build_universe, compute_version

__all__ = [
    "Association",
    "Direction",
    "NodeUniverse",
    "Rank",
    "Source",
    "SourcePins",
    "Taxon",
    "TaxonomyResolver",
    "build_universe",
    "compute_version",
]
