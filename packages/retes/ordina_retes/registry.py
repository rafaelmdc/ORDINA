"""Layer registry (doc 10 A.5).

Adding a modality = adding one ``LayerFactory`` subclass decorated with ``@register`` — no changes
elsewhere (boundary rule A.9 §3). The registry itself is populated in Slice 1+ when the first
factory (phylogeny) lands; it exists now so the seam is fixed.
"""

from __future__ import annotations

# Kept loose until ordina_core.layer.LayerFactory lands in Slice 1. Typed as ``type`` for now
# so this module carries no premature dependency on the (not-yet-written) factory contract.
LAYER_REGISTRY: dict[str, type] = {}


def register[T: type](cls: T) -> T:
    """Register a ``LayerFactory`` subclass by its ``layer_id``."""
    LAYER_REGISTRY[cls.layer_id] = cls  # type: ignore[attr-defined]
    return cls
