"""NodeUniverse — the frozen union node set (doc 10 A.3, decision B5).

The shared node set ``V`` is the UNION of all Disbiome taxa (dual-rank), never the intersection
of what the layers cover (B5). ``version`` is a content hash of the sorted taxids plus the pinned
source versions — the reproducibility key that addresses every downstream artifact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from pydantic import BaseModel

from .association import Association
from .taxon import Rank, Taxon
from .taxonomy import TaxonomyResolver


def compute_version(nodes: Iterable[Taxon], disbiome_snapshot: str, ncbi_version: str) -> str:
    """Deterministic sha256 over the sorted taxids and the source pins.

    Order-independent (taxids are sorted) so two builds of the same taxa + pins hash identically.
    """
    payload = {
        "taxids": sorted(t.taxid for t in nodes),
        "disbiome": disbiome_snapshot,
        "ncbi": ncbi_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


class NodeUniverse(BaseModel):
    """The immutable, versioned set of organism nodes every layer is built against."""

    version: str  # sha256(sorted taxids + source versions) — the reproducibility key
    disbiome_snapshot: str
    ncbi_version: str
    nodes: list[Taxon]

    def genus(self) -> list[Taxon]:
        return [t for t in self.nodes if t.rank == "genus"]

    def species(self) -> list[Taxon]:
        return [t for t in self.nodes if t.rank == "species"]

    def index(self, rank: Rank) -> dict[int, int]:
        """taxid -> row index WITHIN that rank.

        Genus and species are separate node sets / matrices, so each gets its own 0-based index,
        ordered by taxid for stability across rebuilds.
        """
        ranked = sorted(t.taxid for t in self.nodes if t.rank == rank)
        return {taxid: i for i, taxid in enumerate(ranked)}


def build_universe(
    assocs: Iterable[Association],
    tax: TaxonomyResolver,
    *,
    disbiome_snapshot: str,
    ncbi_version: str,
) -> NodeUniverse:
    """Build the union node set from disease–organism associations.

    Every associated taxon is resolved to a ``Taxon``; a species also pulls in its parent genus
    (dual-rank, B1). Unresolvable taxids are skipped. The result is deterministic: nodes are
    sorted by (rank, taxid) and the version hashes the sorted taxids + source pins.
    """
    seen: dict[int, Taxon] = {}
    for a in assocs:
        t = tax.resolve(a.taxid)
        if t is None:
            continue
        seen.setdefault(t.taxid, t)
        if t.rank == "species" and t.parent_genus is not None:
            g = tax.resolve(t.parent_genus)
            if g is not None:
                seen.setdefault(g.taxid, g)

    nodes = sorted(seen.values(), key=lambda t: (t.rank, t.taxid))
    version = compute_version(nodes, disbiome_snapshot, ncbi_version)
    return NodeUniverse(
        version=version,
        disbiome_snapshot=disbiome_snapshot,
        ncbi_version=ncbi_version,
        nodes=nodes,
    )
