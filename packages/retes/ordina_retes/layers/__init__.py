"""Layer factories — one per modality (doc 10 A.5).

Importing this package registers the factories (each is ``@register``-decorated), so the
registry is populated by ``import ordina_retes.layers``.
"""

from __future__ import annotations

from .phylogeny import PhylogenyLayer

__all__ = ["PhylogenyLayer"]
