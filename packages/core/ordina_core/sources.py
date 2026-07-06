"""Source pins — the reproducibility inputs for a build (doc 10 A.3, §9)."""

from __future__ import annotations

from pydantic import BaseModel


class Source(BaseModel):
    """A pinned external source: which database, at which snapshot."""

    name: str  # "disbiome", "gtdb", "ncbi", …
    version: str  # snapshot / pin id
    url: str | None = None


class SourcePins(BaseModel):
    """Pinned source snapshot ids -> reproducible builds.

    Maps a source-db name to its version/snapshot id; passed into every ``LayerFactory.build``.
    """

    pins: dict[str, str]
