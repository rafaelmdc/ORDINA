# ORDINA code workspace

A `uv` workspace of framework-free Python packages (doc [`10` Part A](../docs/10_architecture_and_roadmap.md)).

| Package | Import name | Role |
|---|---|---|
| `packages/core` | `ordina_core` | Domain types shared by every module. No Django, no web imports (boundary rule A.1). |
| `packages/retes` | `ordina_retes` | The science: registry, CLI, layer factories (Slice 1+), multiplex, recovery. No Django. |

> Folder names are short (`core`, `retes`); the Python packages keep the `ordina_` namespace prefix.

## Quickstart

```bash
uv sync                     # install the workspace + dev tools
uv run pytest               # run the tests
uv run ruff check .         # lint
uv run mypy packages/core/ordina_core packages/retes/ordina_retes   # typecheck
```

## Slice 0 — walking skeleton (done)

Build the hashed union `NodeUniverse` (decision B5) from associations + a local NCBI dump:

```bash
uv run ordina build-universe \
  -a packages/retes/tests/fixtures/associations.tsv \
  -t packages/retes/tests/fixtures/taxonomy.tsv \
  -o universe.json
```

`build_universe` takes any `TaxonomyResolver` (protocol in `ordina_core.taxonomy`). Slice 0 uses
`LocalTaxonomyResolver` over a TSV dump; the Braidworks-backed resolver (ncbi weaver) and the
Disbiome `fetch` data path plug into the same seam next, without changing `build_universe`.
