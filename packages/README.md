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

## Slice 1 — one layer to a number (done)

Build the GTDB phylogeny layer, assemble the sparse multiplex, and run the recovery harness
(doc [`09`](../docs/09_recovery_metric.md)) to a `recovery_report.json`. `--fixture` runs the
whole slice offline against Braidworks' bundled GTDB fixture (no download):

```bash
uv run ordina recovery \
  -a packages/retes/tests/fixtures/recovery_associations.tsv \
  -t packages/retes/tests/fixtures/recovery_taxonomy.tsv \
  --fixture --k 2 -o recovery_report.json
```

The layer fetches each organism's `gtdb.tree.rootpath` from Braidworks (a **git dependency**,
pinned in `uv.lock`) and reduces pairs to patristic distance via `gtdb_weaver.cophenetic`. The
report scores the RWR predictor against the nulls (phylogeny, study-effort, degree, …) with a
paired bootstrap CI + permutation test. With only the phylogeny layer the predictor **is** the
phylogeny null, so Slice 1 honestly reports zero lift; the lift is what Slice 2's metabolic
layer must produce at the go/no-go gate.

For a real (non-fixture) run, point the layer at GTDB data with `--gtdb-auto-setup` (downloads
the crosswalk + reference trees) or `--gtdb-db` / `--gtdb-tree`.
