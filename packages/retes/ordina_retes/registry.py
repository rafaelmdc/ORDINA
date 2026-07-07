"""Layer registry (doc 10 A.5).

Adding a modality = adding one ``LayerFactory`` subclass decorated with ``@register`` — no changes
elsewhere (boundary rule A.9 §3). Factories are keyed by ``layer_id`` (e.g. ``phylogeny.gtdb``)
so the CLI can turn ``--layers phylogeny.gtdb`` into the factories that build them.
"""

from __future__ import annotations

from ordina_core import LayerFactory

LAYER_REGISTRY: dict[str, type[LayerFactory]] = {}


def register[T: type[LayerFactory]](cls: T) -> T:
    """Register a ``LayerFactory`` subclass by its ``layer_id``."""
    LAYER_REGISTRY[cls.layer_id] = cls
    return cls
