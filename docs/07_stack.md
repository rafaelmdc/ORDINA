# 07 — Technology stack

> **Scope note.** This fixes stack *decisions and their rationale*, not implementation. Every choice is justified against the four stated priorities — **maintainability, optimization, correctness, ease of implementation** — and carries an explicit *revisit trigger* so we don't over-build now. Where a decision is genuinely open it says so.

## 0. The one fact that decides most of this

Before picking tools, characterize the workload honestly, because the wrong mental model ("it's network-heavy, so we need a graph database") leads to the wrong stack.

ORDINA's multiplex is:

- **Small.** ~10²–10³ organisms (Disbiome has ~800; even generous expansion stays in low thousands of nodes), a handful of layers, so ~10⁴–10⁶ edges *total across all layers*. This fits in memory many times over.
- **Batch-analyzed, not traversal-served.** The expensive work — community detection, cross-layer congruence, random-walk prioritization — is **offline batch computation** over a materialized snapshot, not live multi-hop queries under user load.
- **Provenance-relational at its core.** Evidence, sources, review states, taxonomy, conflict summaries are inherently relational and constraint-heavy. The graph is a *derived view* of that relational truth, not the system of record.
- **Read-mostly at serve time.** The frontend shows precomputed networks, module memberships, and rankings. Interactive exploration is neighborhood-scale.

**Consequence:** keep a relational system of record, compute graphs in memory with C-backed libraries, materialize results, and serve those. A dedicated graph database would add a second stateful system and dual-write/sync burden to accelerate queries we mostly precompute — a poor trade at this scale. (Revisit trigger in §5.)

## 1. Decisions at a glance

| Concern | Decision | One-line why |
|---|---|---|
| Frontend | **React + TypeScript + Tailwind + Vite** | Your call, and correct; TS for correctness, Vite for DX. |
| Graph rendering | **Cytoscape.js** (interactive) + **Sigma.js/deck.gl** if scale demands | Keeps existing Cytoscape work; Sigma/WebGL only if node counts explode. |
| API / backend | **Django + Django Ninja** | One backend (Mind already Django); Ninja gives FastAPI-style typed async APIs on top. Best of both. |
| System of record | **PostgreSQL** | Provenance/review/taxonomy are relational; JSONB + materialized views cover the flexible/derived parts. |
| Graph DB | **None (for now)** | Small batch-analyzed graph; Postgres + in-memory analysis wins. Cypher-if-ever → Apache AGE, not Neo4j (§5). |
| Graph analysis | **python-igraph** (primary), **graph-tool** (optional heavy), **MultiXrank**, **leidenalg** | C/C++ cores; multiplex-capable; MultiXrank is purpose-built for our RWR. |
| Data wrangling | **Polars** (+ numpy/scipy sparse) | Rust-backed speed with a clean API; scipy sparse for supra-adjacency matrices. |
| Rust/Cython | **Not upfront** — via Polars now; **PyO3/maturin** only for a profiled hotspot | Heavy math already lives in C libraries; don't write our own until profiling proves need. |
| Heavy pipelines | **Nextflow** (offline enrichment/analysis DAG) | Field-standard reproducible parallelism; the metabolic modelling is embarrassingly parallel. |
| App async jobs | **Python task queue** (Prefect or Celery) — part of Flux, later | App-triggered imports/recompute ≠ heavy bioinformatics DAG; keep them separate. |
| Packaging/env | **uv** (Python), **Docker Compose** (services), pinned envs | Fast, reproducible; matches Braidworks' own `uv` workspace. |

## 2. Frontend — React + Tailwind (confirmed)

- **React + TypeScript + Tailwind + Vite.** TypeScript is a correctness lever (typed API client generated from the backend schema); Tailwind keeps styling maintainable without a bespoke design system; Vite for fast builds.
- **Graph visualization:** start with **Cytoscape.js** (already used in the current app, good for interactive neighborhood/module views). If a view needs to render many thousands of nodes at once, move *that view* to **Sigma.js** or **deck.gl** (WebGL) — don't switch wholesale. Heavy layout computation happens server-side (precomputed positions), not in the browser.
- **Contract-first:** the React app consumes a typed API. Generate the TS client from the backend's OpenAPI schema so frontend/backend stay in sync (a correctness win Django Ninja gives for free).

## 3. Backend framework — Django + Django Ninja

You leaned Django "if we ever want users," and that's the right instinct:

- **Mind is already Django**, so this is continuity, not a rewrite.
- **Users, auth, admin, migrations, an ORM with real constraints** — all first-class in Django. **Curia** (human review) benefits enormously from Django admin scaffolding; **Flux** benefits from Django's migration/ORM discipline for provenance tables.
- **Django Ninja** layers a FastAPI-style experience on top: Pydantic schemas, typed request/response, async endpoints, auto OpenAPI. So we get FastAPI's ergonomics *and* Django's batteries — without maintaining two frameworks or rebuilding auth/admin.
- **Why not plain FastAPI:** it's excellent for a thin async service, but we'd re-implement auth, admin, migrations, and ORM discipline that Django already gives — a maintainability loss for a project that explicitly wants longevity and eventual users.
- *Alternative if async throughput ever dominates:* DRF is heavier/sync-oriented; Ninja is the better default. Plain FastAPI only if ORDINA ever splits a high-throughput compute microservice out of the Django monolith (not now).

## 4. Database — PostgreSQL

**System of record = Postgres.** Rationale and tactics:

- **Relational truth:** studies, groups, comparisons, findings, sources, review states, taxonomy closure — all relational with strong constraints (the current Mind schema already encodes good uniqueness/check constraints). Keep that.
- **Flexible bits → JSONB:** per-source raw payloads, provenance blobs, and heterogeneous layer metadata live in JSONB columns, indexed with GIN where queried.
- **Taxonomy:** keep the existing `TaxonClosure` table (works well for rollup); `ltree` is an alternative but the closure table is already fit-for-purpose.
- **Derived graphs → materialized:** graph edge summaries and layer snapshots are **materialized views or snapshot tables** refreshed by batch jobs, not recomputed per request. This is the performance backbone for serving.
- **Snapshots for analysis:** each analysis run reads a *versioned, immutable* snapshot (a set of tables or exported Parquet/Arrow artifacts) so results are reproducible and provenance-stamped.

## 5. Why no graph database (and the Cypher question, answered)

You flagged this as uncertain and asked specifically about Cypher. Direct answer:

- **At this scale, a graph DB (Neo4j/Memgraph) is net-negative.** It's a second stateful system requiring dual-write/sync from the relational truth, and its strength — fast live multi-hop traversal — is not our bottleneck (we precompute analytics and serve neighborhood-scale views, which Postgres recursive CTEs or in-memory adjacency handle fine).
- **Graph DBs are also *not* where heavy analytics run.** Community detection and RWR are matrix/graph-algorithm batch jobs, done far better in igraph/graph-tool/scipy/MultiXrank than in Cypher.
- **If you ever genuinely want Cypher queries**, prefer **Apache AGE** (openCypher *inside* Postgres) over adding Neo4j — you get graph queries without a second database or a sync pipeline.
- **Revisit trigger for a real graph DB (Memgraph, in-memory + Cypher):** only if (a) the graph grows well beyond memory-comfortable size, *and* (b) live, deep, ad-hoc multi-hop traversal becomes a core UX need that precompute + CTEs can't serve. Until both are true, it's complexity we don't need.

## 6. Graph analysis stack

- **python-igraph** — primary. C core, trivial `uv`/pip install, handles millions of edges, supports weighted edges and per-edge/-layer attributes (so a multiplex is one graph with a `layer` attribute, or a list of graphs over shared vertices). Community detection (Leiden via **leidenalg**, Louvain, Infomap), centrality, projections all included.
- **graph-tool** — optional, for the heaviest jobs. Fastest available (C++/Boost, parallel), best stochastic-block-model tooling — but a painful conda/system install. Introduce *only* if igraph becomes a measured bottleneck; keep it behind the same internal graph interface so it's swappable.
- **MultiXrank** — purpose-built Random Walk with Restart on multilayer networks (our §04 prioritization). Use directly rather than reimplementing RWR.
- **Multiplex community detection** — **MolTi** (external C++, multiplex-modularity) for the canonical method from §04; leidenalg/igraph for multilayer/aggregated variants. Wrap MolTi as a pipeline step (§8), not an in-process call.
- **scipy.sparse** — supra-adjacency and layer-coupling matrices live here; most custom cross-layer math is sparse linear algebra, which scipy/numpy already vectorize in C/BLAS.
- **networkx** — convenience/prototyping only; *not* for hot paths (pure-Python, slow). It was already removed from Mind for good reason.

## 7. Data wrangling and the Rust/Cython question

- **Polars** (Rust-backed) for tabular ETL between Postgres, Braidworks outputs, and the graph builders — big speed and memory wins over pandas with a cleaner, more correct (typed, lazy) API. This is the "Rust inside Python" you asked about, obtained for free via a mature library.
- **numpy / scipy** for numerical/sparse work (C/BLAS/LAPACK under the hood).
- **Writing our own Rust/Cython?** *Not upfront.* The heavy lifting already lives in C/C++/Rust libraries (igraph, graph-tool, scipy, Polars). Write a **PyO3/maturin** Rust extension (or Cython) **only** for a specific hot loop that (a) profiling proves dominates runtime and (b) can't be vectorized in numpy/scipy or pushed into igraph. Likeliest future candidate: a bespoke pairwise layer-similarity or metabolic-complementarity kernel over many organism pairs — and even that should try scipy/`numba` first. Premature Rust is a maintainability tax.

## 8. Parallelization and orchestration — Nextflow, yes, but scoped

You asked about Nextflow. It's a good fit **for the right layer**, and the key is not to use one tool for two different jobs:

- **Offline enrichment + analysis DAG → Nextflow.** Building the metabolic layer means running genome-scale tools (AGORA/CarveMe reconstructions, SMETANA/MICOM community modelling) **per organism / per organism-pair** — embarrassingly parallel, heavy, reproducibility-critical bioinformatics. Nextflow is the field standard here: content-addressed caching, resume, container-per-process, cluster/cloud executors. GTDB placement, antiSMASH/gutSMASH runs, **abundance co-occurrence network inference** (SPIEC-EASI/SparCC/FlashWeave over `curatedMetagenomicData`/GMrepo abundance tables — see [`08`](08_decisions.md) C1), and community-detection parameter sweeps all fit the same DAG model. This is where "ease of parallelization" actually pays off.
  - *Lighter alternative:* **Snakemake** (Python-native, gentler learning curve) if the full Nextflow/JVM toolchain feels heavy. Recommendation: **Nextflow** for the bioinformatics-heavy metabolic/genomic steps (best ecosystem, nf-core modules), reconsider Snakemake if the team prefers Python-only.
- **App-triggered async jobs → a Python task queue (Prefect or Celery), part of Flux.** Importing a Disbiome refresh, resolving taxa, recomputing an affected graph summary after review — these are short, transactional, DB-coupled jobs that belong to the web app, *not* to a Nextflow DAG. Keep them in a Python queue. **Prefect** (modern, typed, good observability) is the recommended default; **Celery** if we want the most battle-tested option. This is designed ground-up as part of Flux later.

Rule of thumb: **Nextflow computes the science (offline, heavy, parallel, reproducible); the Python queue runs the app (online, light, transactional).** They meet at the database and the snapshot artifacts.

## 9. Correctness and reproducibility (a first-class concern)

- **Typed boundaries:** Pydantic/Ninja schemas at the API; Polars/typed models internally; generated TS client on the frontend. Types catch a whole class of integration bugs.
- **Database constraints as invariants:** keep and extend Mind's uniqueness/check constraints; represent conflict/direction on edges (never by node duplication) so the graph can't encode contradictions structurally.
- **Testing:** `pytest` for units/integration; **Hypothesis** (property-based) for graph invariants (e.g. "rollup never drops an organism", "a summary edge's counts equal the sum of its evidence edges", "no self-loops in projection X"); golden-file tests for pipeline outputs.
- **Reproducible pipelines:** Nextflow's content-addressable cache + pinned containers; every analysis reads an immutable versioned snapshot and writes provenance (source versions, code commit, parameters). A result you can't regenerate isn't a result.
- **Determinism where it matters:** seed the randomized algorithms (MolTi randomization, RWR sampling) and record seeds.
- **CI:** lint (ruff), type-check (mypy/pyright, tsc), test, and a small end-to-end smoke pipeline on every change.

## 10. Deployment shape

- **Docker Compose** for local/dev: `web` (Django+Ninja), `db` (Postgres), `frontend` (Vite dev / static build), and later `worker` (Prefect/Celery) + `redis` (broker/cache) as Flux lands. Nextflow runs as its own invocation (local executor in dev; cluster/cloud in production), writing artifacts the web stack reads.
- **uv** for Python dependency/lockfile management (fast, reproducible, and consistent with Braidworks' own tooling).
- Redis enters only when Flux needs a broker/cache — not before.

## 11. What we are explicitly NOT doing yet

To respect "ease of implementation" and avoid the over-engineering trap:

- No graph database (§5). No microservices — one Django backend. No Kubernetes — Compose until scale demands otherwise. No custom Rust/Cython until profiled (§7). No Kafka/streaming — batch snapshots suffice. No Flux/Curia build yet (designed ground-up later); this doc only reserves their slots in the stack.

## 12. Mapping to the module map

| Module | Stack footprint |
|---|---|
| **Mind** | Django + Postgres + Django Ninja read APIs; the relational system of record. |
| **Retes** | Snapshot reader + igraph/graph-tool/MultiXrank/MolTi analysis, orchestrated by Nextflow; results materialized to Postgres/Arrow and served via Ninja to the React graph views. |
| **Flux** | Python task queue (Prefect/Celery) + Redis + Braidworks connectors; source sync, taxon resolution, snapshot/graph recompute. Ground-up later. |
| **Curia** | Django admin-derived review UI (or React screens over Ninja endpoints); review-state transitions on evidence. |

---

**Net:** one maintainable Django backend, a React/TS/Tailwind frontend, Postgres as truth, C/Rust-backed libraries (igraph, Polars, scipy, MultiXrank) for speed without bespoke native code, Nextflow for the heavy reproducible science, and a Python queue for app async — with graph-DB, custom Rust, and extra infrastructure all deferred behind explicit triggers.
