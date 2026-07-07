"""Multiplex — the assembled sparse network the recovery walk runs on (doc 10 A.5).

A plain compute container (holds sparse matrices; not a serializable schema). :func:`assemble`
maps each :class:`~ordina_core.BuiltLayer`'s edges onto one shared node indexing at a given
rank, giving one square adjacency per layer. :meth:`Multiplex.supra_adjacency` stacks them into
the ``L·N × L·N`` supra-adjacency (diagonal blocks = layers, off-diagonal blocks = inter-layer
coupling) that a random walk with restart traverses across layers.
"""

from __future__ import annotations

from dataclasses import dataclass

from ordina_core import BuiltLayer, Coverage, NodeUniverse, Rank
from scipy import sparse


@dataclass
class Multiplex:
    """Sparse adjacency per layer over one shared node set, plus its coverage masks."""

    universe: NodeUniverse
    rank: Rank
    order: list[int]  # taxids in row/column order (taxid-sorted, matches universe.index(rank))
    layers: dict[str, sparse.csr_matrix]  # layer_id -> adjacency on ``order``
    coverage: dict[str, Coverage]  # layer_id -> which nodes it measured

    @property
    def n(self) -> int:
        return len(self.order)

    def supra_adjacency(self, coupling: float) -> sparse.csr_matrix:
        """The ``L·N × L·N`` supra-adjacency: layer blocks on the diagonal, ``coupling·I`` off it.

        Layers are ordered as ``self.layers`` iterates. With one layer this is just that layer's
        adjacency (no coupling term). ``coupling`` is the inter-layer weight that lets the walk
        hop between a node's copies across layers.
        """
        ids = list(self.layers)
        size = len(ids)
        blocks: list[list[sparse.spmatrix | None]] = [[None] * size for _ in range(size)]
        for i, layer_id in enumerate(ids):
            blocks[i][i] = self.layers[layer_id]
            for j in range(size):
                if i != j:
                    blocks[i][j] = coupling * sparse.identity(self.n, format="csr")
        return sparse.bmat(blocks, format="csr")


def assemble(u: NodeUniverse, built: list[BuiltLayer], rank: Rank = "genus") -> Multiplex:
    """Assemble built layers into a :class:`Multiplex` on the universe's ``rank`` node set.

    Every layer must be built at ``rank`` (genus is primary, B1). Undirected layers are
    symmetrized; directed ones keep their orientation. Edges to taxids outside the node set
    are dropped (defensive — a layer's edges should already live on the universe).
    """
    index = u.index(rank)
    order = sorted(index, key=lambda taxid: index[taxid])
    size = len(index)
    layers: dict[str, sparse.csr_matrix] = {}
    coverage: dict[str, Coverage] = {}
    for layer in built:
        if layer.manifest.rank != rank:
            raise ValueError(
                f"layer {layer.manifest.layer_id!r} is rank {layer.manifest.rank!r}, "
                f"cannot assemble at {rank!r}"
            )
        rows: list[int] = []
        cols: list[int] = []
        data: list[float] = []
        for a, b, weight in layer.edges:
            i, j = index.get(a), index.get(b)
            if i is None or j is None:
                continue
            rows.append(i)
            cols.append(j)
            data.append(weight)
            if not layer.manifest.directed:
                rows.append(j)
                cols.append(i)
                data.append(weight)
        layers[layer.manifest.layer_id] = sparse.csr_matrix(
            (data, (rows, cols)), shape=(size, size)
        )
        coverage[layer.manifest.layer_id] = layer.coverage
    return Multiplex(universe=u, rank=rank, order=order, layers=layers, coverage=coverage)
