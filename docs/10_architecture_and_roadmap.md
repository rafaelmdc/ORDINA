# 10 — Architecture and build plan

> The bridge from docs to running code. **Part A** is the concrete architecture (packages, types, tables, endpoints). **Part B** is the build plan as **vertical slices** — each slice is a thin end-to-end thing that runs, not a horizontal layer. The ordering puts the go/no-go recovery test ([`09`](09_recovery_metric.md), decision [`08`](08_decisions.md) A2) as early as a real answer is possible.
>
> Signatures below are the *intended shape*, not final APIs. Type hints use Pydantic models and Polars (`pl.DataFrame`) per the stack ([`07`](07_stack.md)).

---

## Part A — Architecture

### A.1 One principle: a framework-free core

The domain types live in **one package with no Django and no web imports**, so the CLI, the offline pipeline, the Celery workers, and the web API all import the *same* objects. Business rules exist once. Concretely: `ordina-core` has zero dependency on Django; `ordina-retes` (all the science) has zero dependency on Django; only `ordina-mind` and `ordina-flux` may import Django.

### A.2 Repository layout (a `uv` workspace)

```
ordina/
  pyproject.toml                 # uv workspace root
  packages/
    ordina-core/                 # domain types, no frameworks
      ordina_core/
        taxon.py  universe.py  layer.py  run.py  provenance.py  sources.py
    ordina-retes/                # the science: factories, multiplex, analysis, recovery
      ordina_retes/
        registry.py  multiplex.py
        layers/ phylogeny.py  metabolic.py  ecophysiology.py  cooccurrence.py  disease.py
        analysis/ communities.py  walk.py  congruence.py
        recovery/ split.py  predict.py  metrics.py  baselines.py  harness.py
        cli.py                   # `ordina` command (Typer)
    ordina-mind/                 # Django project + Django Ninja API
      ordina_mind/ settings.py  models.py  api.py  tasks.py
    ordina-flux/                 # headless ingestion (A.7)
      ordina_flux/ models.py  tasks.py  api.py  statemachine.py
  pipeline/                      # Nextflow (A.8)
    main.nf  modules/*.nf
  web/                           # React + Vite + Cytoscape.js (frontend for Retes + Curia)
```

### A.3 `ordina-core` — the types everything shares

```python
# taxon.py
Rank = Literal["genus", "species"]

class Taxon(BaseModel):
    taxid: int
    rank: Rank
    name: str
    parent_genus: int | None          # genus taxid for a species; None for a genus row

# universe.py — the frozen union node set (decision B5)
class NodeUniverse(BaseModel):
    version: str                       # sha256(sorted taxids + source versions) — the reproducibility key
    disbiome_snapshot: str
    ncbi_version: str
    nodes: list[Taxon]
    def genus(self)   -> list[Taxon]
    def species(self) -> list[Taxon]
    def index(self, rank: Rank) -> dict[int, int]   # taxid -> row index WITHIN that rank
                                                    # (genus & species are separate node sets / matrices)

def build_universe(assocs: Iterable[Association], tax: TaxonomyResolver) -> NodeUniverse

# association.py — the flattened disease–organism evidence row
#   (a projection of Mind's QualitativeFinding, doc 01; NOT a second source of truth, A.6)
class Association(BaseModel):
    disease_meddra: str                # working key in iteration 1 (Disbiome-only), decision D1
    disease_mondo: str | None          # nullable; filled from the confirmed crosswalk (data/disease_mapping)
    taxid: int
    direction: Literal["enriched", "depleted"]   # projected from Mind's QualitativeFinding.Direction:
                                       # enriched|increased|elevated -> "enriched";
                                       # depleted|decreased|reduced  -> "depleted".
                                       # Mind has NO "unchanged" state; a neutral quantitative
                                       # value, if ever needed, comes from QuantitativeFinding.
    source: str                        # "disbiome", "gmrepo", …
    evidence_ref: str

# layer.py — the layer factory contract (concrete form of doc 03 §1a)
CoverageState = Literal["present", "measured_absent", "unmeasured"]
EdgeSemantics = Literal["similarity", "directed_exchange", "signed_cosignature"]

class LayerManifest(BaseModel):
    layer_id: str                      # "phylogeny.gtdb"
    layer_version: str                 # hash of PINNED INPUTS (built_on + source pins + params + seed
                                       # + code_version) — the deterministic address, not an output hash
    built_on: str                      # NodeUniverse.version it was built against
    native_rank: str; aggregation_rule: str
    directed: bool                     # true -> asymmetric matrix (e.g. metabolic exchange)
    edge_semantics: EdgeSemantics
    sources: list[Source]
    fetch_want: list[str]              # target strand-type(s) fetched via braidworks.fetch (A.4)
    edge_rule: str; weight_metric: str
    normalization: Normalization       # {method, params, applied}
    null_model: NullModel
    seed: int | None                   # RNG seed for stochastic steps, recorded
    determinism: Literal["exact", "seeded_tolerant"]   # doc 03 §1a
    n_edges: int; n_measured_nodes: int
    output_check: str                  # "exact" -> content digest asserted bitwise on rebuild;
                                       # "seeded_tolerant" -> a NUMERIC fingerprint compared within
                                       # tolerance ε (you cannot put a tolerance on a hash)

class BuiltLayer(BaseModel):
    manifest: LayerManifest
    edges:    pl.DataFrame             # cols: rank, src, dst, w_raw, w_norm, sign, evidence_ref
                                       #   (sign in {+1,-1,None}; src/dst order meaningful iff directed)
    coverage: pl.DataFrame             # cols: rank, taxid, state   (three-state, one row per node)

class SourcePins(BaseModel):           # pinned source snapshot ids -> reproducible builds
    pins: dict[str, str]               # source db -> version/snapshot id

class LayerFactory(ABC):
    layer_id: str
    @abstractmethod
    def declare(self) -> LayerManifest: ...                       # metadata only, no data fetch
    @abstractmethod
    def build(self, u: NodeUniverse, sources: SourcePins) -> BuiltLayer: ...
    def validate(self, layer: BuiltLayer) -> None:   # shared, concrete asserts:
        # - every universe node has exactly one coverage state (no missing / dup)
        # - no edge references a taxid outside the universe
        # - all w_norm in [0,1]; sign in {+1,-1,None}; directed consistent with edge_semantics
        # - a rebuild from the same pinned inputs + seed passes output_check: "exact" layers
        #   reproduce the digest bitwise; "seeded_tolerant" layers reproduce a numeric fingerprint
        #   within tolerance ε (doc 03 §1a). NOT "reproduces layer_version" — that is an input
        #   hash, so it is trivially always true and checks nothing.
```

The **scalar** core models (`Taxon`, `LayerManifest`, `Association`, coverage/run rows) double as **Django Ninja response schemas** — Ninja is Pydantic-native, so there's no second serializer layer. The **bulk arrays** are *not* API schemas: `BuiltLayer.edges`/`coverage` are Polars DataFrames and the `Multiplex` layers are scipy sparse matrices — in-memory/on-disk compute artifacts served as **Parquet**, never inline JSON. (`BuiltLayer` is still a Pydantic model for internal use, with `arbitrary_types_allowed` for its DataFrame fields.)

### A.4 External data access — through Braidworks, called generically

ORDINA never calls external databases directly. It depends on **Braidworks**, the project's data-access library: given identifiers you have, it plans a route across its weavers to the data you want and returns it. The only surface ORDINA uses is the **`fetch` facade** (a thin convenience over Braidworks' `plan/execute` core, added to `braidworks-core` for this project and shipped there):

```python
braidworks.fetch(want: str | list[str], ids: list[str], *, have: str = "ncbi.taxon.id",
                 params=..., registry=...) -> FetchResult
#   FetchResult.resolved:   dict[id -> {want_type: value}]
#   FetchResult.unresolved: list[id]     # ids that produced nothing -> the coverage-gap signal
#   FetchResult.column(t):  dict[id -> value]   # convenience for a single want-type
```

`want` is a **target strand-type**, not a route string — the real produced keys, e.g. `"microbe.metabolism.reactions"` (agora weaver), `"microbe.trait.oxygen_tolerance"` (bacdive), `"microbe.ecology.functional_groups"` (faprotax), `"gtdb.tree.rootpath"` (the new capability, [`03`](03_layer_factory_and_catalog.md) §3.3). Each `LayerFactory.build()`'s first step is one `fetch(want, ids)` call; nothing else in ORDINA opens a network connection. Pass a shared `registry` across a build to skip re-discovery. A source ORDINA lacks = a new weaver/capability added in Braidworks, not new code here.

**Per-layer fetch map** (all `have="ncbi.taxon.id"`):

| Layer | `want` (real strand-type) | Weaver | Then ORDINA builds |
|---|---|---|---|
| `metabolic.repertoire` | `microbe.metabolism.reactions` | agora (AGORA2) | Jaccard over reaction sets |
| `ecophysiology` | `microbe.trait.*`, `microbe.ecology.functional_groups` | bacdive, faprotax | trait-vector similarity |
| `phylogeny` | `gtdb.tree.rootpath` *(new capability)* | gtdb | `1 − dist/diameter`; pairwise cophenetic reduced client-side |
| disease target | `microbe.disease.records` | disbiome | seed/truth sets + co-signature |

`metabolic.complementarity` is **not** in this table — it is an offline solver step (SMETANA/MICOM over paired AGORA2 SBML), not a `fetch` (A.8, [`03`](03_layer_factory_and_catalog.md) §3.1).

### A.5 `ordina-retes` — factories, multiplex, analysis, recovery

```python
# registry.py
LAYER_REGISTRY: dict[str, type[LayerFactory]] = {}
def register(cls): LAYER_REGISTRY[cls.layer_id] = cls; return cls

# layers/phylogeny.py — a factory is ~50 lines
@register
class PhylogenyLayer(LayerFactory):
    layer_id = "phylogeny.gtdb"
    def build(self, u, sources):
        # Braidworks is per-entity, so we fetch each leaf's tree placement (gtdb.tree.rootpath)
        # and do the PAIRWISE patristic reduction here, via gtdb_weaver.cophenetic (doc 03 §3.3).
        res   = braidworks.fetch("gtdb.tree.rootpath",
                                 ids=[str(t.taxid) for t in u.species()], registry=reg)
        edges = self._genus_edges(res.resolved, u)               # cophenetic -> 1 - dist/maxdist
        cov   = self._coverage(res, u)                           # res.unresolved -> 'unmeasured'
        return BuiltLayer(manifest=..., edges=normalize(edges), coverage=cov)

# multiplex.py — a plain compute container (holds sparse matrices; NOT a serializable schema)
@dataclass
class Multiplex:
    universe: NodeUniverse
    rank:     Rank
    layers:   dict[str, sparse.csr_matrix]              # layer_id -> adjacency on universe.index(rank);
                                                        # asymmetric where manifest.directed is true
    def supra_adjacency(self, coupling: float) -> sparse.csr_matrix
def assemble(u: NodeUniverse, built: list[BuiltLayer], rank: Rank = "genus") -> Multiplex

# recovery/ — the harness spelled out in doc 09.
# NOTE: the headline predictor is ENRICHMENT layers only — the disease co-signature layer is
# target-side and excluded (doc 09 §2), so these layers are disease-independent and need NO
# per-fold rebuild; only the seed (kept links) and truth (hidden links) change per split.
def grouped_kfold(assocs, disease_groups, k=5) -> list[Split]     # split.py; look-alike diseases grouped
def temporal_split(old, new) -> Split
def predict(m: Multiplex, seed_taxa: list[int]) -> list[tuple[int, float]]   # RWR/MultiXrank; seed = a
                                                                            # disease's KEPT partner organisms
def recall_at_k(ranked, truth, k) -> float                       # metrics.py
def r_precision(ranked, truth) -> float                          # precision at k=len(truth) — fair per disease
def auprc(ranked, truth) -> float
def baseline_phylogeny(m, seed_taxa) -> list[tuple[int,float]]    # baselines.py
def baseline_study_effort(train_assocs) -> list[tuple[int,float]]  # rank by TRAINING studiedness only
def baseline_enrichment_coverage(m, train_assocs) -> list[tuple[int,float]]  # rank by biology carried
def baseline_degree_random(m, seed_taxa) -> list[tuple[int,float]]
def control_propagation_only(m, seed_taxa) -> list[tuple[int,float]]  # genus rollup, biology stripped
def run_recovery(m, splits, baselines) -> RecoveryReport         # harness.py; PAIRED bootstrap CIs,
                                                                 # permutation check, pre-registered primary
```

Analysis: `communities.py` wraps MolTi/generalized-Louvain; `walk.py` wraps MultiXrank for the served disease→organism query; `congruence.py` computes predicted-vs-observed overlap ([`05`](05_validation.md) §4b).

### A.6 `ordina-mind` — Postgres tables + Ninja endpoints

**Tables** (Django models → PostgreSQL):

| Table | Key columns |
|---|---|
| `taxon` | `taxid` PK, `rank`, `name`, `parent_genus` |
| `association` | `id` PK, `disease_meddra` (working key), `disease_mondo` (nullable, filled from the confirmed crosswalk), `taxid`, `direction`, `source`, `snapshot`, `evidence` (JSONB) |
| `layer_manifest` | `layer_version` PK, `layer_id`, `built_on`, `manifest` (JSONB) |
| `layer_coverage` | (`layer_version`, `rank`, `taxid`) PK, `state` |
| `run` | `id` PK, `universe_version`, `layer_versions` (array), `created_at` |
| `run_result` | (`run_id`, `kind`) PK, `payload` (JSONB) — e.g. `kind="recovery"`, ranked lists |

**`association` is a derived view, not a second source of truth.** Mind's normalized evidence model stays as it is today — `Study → Group → Comparison → QualitativeFinding(taxon, direction)` ([`01`](01_mind_data_foundation.md)). The `association` table is the **flattened disease–organism projection** that Retes consumes (one row per disease–taxon–direction, with `evidence` JSONB pointing back to the `QualitativeFinding` rows it was rolled up from). It is rebuilt from the normalized tables, never edited directly — so there is one system of record, plus a convenience projection for the network build.

Layer **edge lists** are large and numeric → stored as Parquet in object storage, addressed by `layer_version`; only the manifest + coverage live in Postgres (so "which layers measured this taxon?" is a SQL query).

**Endpoints** (Django Ninja, returning `ordina-core` schemas directly):

```
GET  /api/taxa?rank=genus
GET  /api/layers                              -> [LayerManifest]
GET  /api/layers/{layer_version}/coverage?taxid=
GET  /api/associations?disease={id}           -> id is a MONDO id OR a native MedDRA code
GET  /api/runs/{id}                           -> run + results
POST /api/runs/{id}/seed  {disease}           -> ranked, layer-explained organisms; disease = MONDO id
                                                 or MedDRA code (MONDO is nullable in iteration 1, D1)
                                                 (dispatched to Celery; A.8)
```

### A.7 `ordina-flux` — headless ingestion

Flux is an **ingestion engine, not a web app**: Celery/Prefect workers plus a *small* trigger/status API, **no frontend**. The review UI (Curia) is separate and sits on Flux's API.

**State machine** (`raw source record → candidate → reviewed evidence`, from [`01`](01_mind_data_foundation.md)):

| Table | Columns / states |
|---|---|
| `raw_record` | `id`, `source`, `payload` (JSONB), `fetched_at`, `state` ∈ {fetched, normalized, error} |
| `candidate` | `id`, `raw_id`, `normalized` (JSONB), `state` ∈ {pending, accepted, rejected} |
| `review` | `candidate_id`, `decision`, `reviewer`, `at` |

```python
# tasks.py (Celery)
@task def ingest_source(source: str)          # fetch via braidworks -> raw_record rows
@task def normalize(raw_id: int)              # raw -> candidate (map to Taxon/MONDO)
@task def promote(candidate_id: int)          # accepted candidate -> association (trusted)
# api.py (Ninja, internal)
POST /flux/ingest  {source}   -> job_id
GET  /flux/status/{job_id}
```

Trusted `association` rows are the only ones Mind serves; candidates never mix into trusted data until `promote`.

### A.8 Offline pipeline (Nextflow) and the online split

Heavy, reproducible compute runs offline as a **Nextflow DAG**; the web tier only serves the result and runs one interactive query type (seeding a walk) via Celery.

```
build_universe        -> universe.json (hashed)
build_layer  (scatter over layer_ids, parallel) -> layer_{id}.parquet + manifest
assemble_multiplex    -> multiplex artifact
run_recovery          -> recovery_report.json
publish               -> load manifests+coverage+results into Postgres, edges to object store
```

Everything is addressed by `(universe.version, {layer_version})` — re-running `publish` on the same hashes reproduces the exact served network.

### A.9 The boundary rules (what keeps it maintainable)

1. Only `ordina-mind` / `ordina-flux` import Django. `core` and `retes` are framework-free and runnable from the CLI.
2. All external data enters via `braidworks.fetch`; no second data-access layer.
3. Every layer is a `LayerFactory` subclass registered in `LAYER_REGISTRY`; adding a modality = adding one file, no changes elsewhere.
4. `ordina-core` Pydantic models are the API schemas — no duplicated serializers.
5. Compute is offline + content-hashed; the web tier is thin.

---

## Part B — Build plan (vertical slices)

Each slice runs end-to-end and produces a checkable artifact. The gate is Slice 2.

> **Disease vocabulary is NOT on the critical path.** The multiplex is organism-keyed, and iteration 1 is Disbiome-only, so diseases are keyed by their **native MedDRA code**; MONDO ([`08`](08_decisions.md) D1) is a normalization layer added only when a *second* disease source (GMrepo/gutMDisorder) arrives. An **interim Disbiome→MONDO crosswalk already exists** (`data/disease_mapping/` — 222 confirmed, 77% of experiments); a deterministic UMLS-based pass is a pending follow-up. So `association` keys by MedDRA now, with a **nullable `disease_mondo`** filled from the confirmed crosswalk. Until MONDO lands, the recovery split's look-alike-disease grouping uses the **shared-organism-overlap fallback** (§ recovery note below).

### Slice 0 — Walking skeleton: universe from a file
- **Build:** the `uv` workspace; `ordina-core` types (A.3); a `TaxonomyResolver` over a local NCBI dump; `ordina build-universe --out universe.json`.
- **Runs end-to-end:** Disbiome dump → resolve ranks → hashed `NodeUniverse` on disk.
- **Done when:** `ordina build-universe` emits a `universe.json` with genus+species nodes and a stable `version`; `ordina-core` has unit tests and imports with no Django.

### Slice 1 — One layer to a number (the harness is real)
- **Prerequisite (Braidworks) — ✅ done:** the reference-tree capability ([`03`](03_layer_factory_and_catalog.md) §3.3). Built as `gtdb_weaver`'s **`describe_gtdb_tree_placement` → `gtdb.tree.rootpath`** (per-entity leaf placement) plus the `gtdb_weaver.cophenetic` reducer, rather than a literal pairwise `gtdb.patristic_distance` want — Braidworks stays strictly per-entity (no core change), and the pairwise reduction lives in the layer. Verified end-to-end against live GTDB (R232): the tree URLs, the metadata-accession↔leaf join, the parser on the real ~190k-leaf tree, and phylogeny-tracking distances.
- **Build — ✅ done:** `ordina-retes` registry; `PhylogenyLayer` (via `braidworks.fetch("gtdb.tree.rootpath")` + client-side cophenetic, genus-primary aggregation); `assemble()` → `Multiplex` (scipy.sparse); the full recovery harness (grouped k-fold, `predict` via RWR, `recall_at_k`/`r_precision`/`auprc`, the nulls, paired bootstrap + permutation); `ordina recovery --layers phylogeny.gtdb` → `recovery_report.json`. Braidworks is a git dependency; `--fixture` runs the whole slice offline.
- **Runs end-to-end:** universe → build one layer → assemble → score vs baselines.
- **Done when:** it prints Recall@k / AUPRC for `{phylogeny}` and the baselines; the phylogeny run ≈ the phylogeny baseline (sanity that the pipe is wired right); rebuilding the layer passes its `output_check` (exact digest); **and the harness passes a planted-signal discrimination test** — inject a synthetic layer wiring a known set of organisms to a fake disease's seeds and confirm the harness ranks them top while the baselines don't, *and* the label-permutation check collapses the signal. This proves the harness *discriminates*, not merely *runs*, before the real gate rides on it (finding 12).

### Slice 2 — ⛳ The gate: metabolic + disease target → go/no-go
- **Build:** `MetabolicRepertoireLayer` (via `braidworks.fetch("microbe.metabolism.reactions")`, Jaccard over AGORA2 reaction sets — the feasible metabolic layer; `metabolic.complementarity` is deferred to Slice 4, [`03`](03_layer_factory_and_catalog.md) §3.1); the **disease target** = seed/truth sets derived from `association` rows (a disease's partner organisms), fed to the harness — note the disease co-signature layer is **target-side, not walked** in the headline metric ([`09`](09_recovery_metric.md) §2), so the enrichment predictor is disease-independent and needs no per-fold rebuild; disease-group clustering feeding `grouped_kfold` (look-alike diseases kept together — using the **shared-organism-overlap fallback** while MONDO is deferred, swappable for the MONDO hierarchy later without changing the harness); wrap Slices 0–2 build steps in the **Nextflow** DAG (`build_universe → build_layer → assemble → run_recovery`).
- **Runs end-to-end:** the whole offline pipeline producing `recovery_report.json`.
- **Done when:** the report gives `{phylogeny + metabolic}` vs both nulls with **paired** bootstrap CIs, the temporal split (if available — [`09`](09_recovery_metric.md) §3), and the permutation check — i.e. the **A2 decision** ([`09`](09_recovery_metric.md) §10):
  - **Pass →** continue to Slice 3+.
  - **Fail →** stop and diagnose on two layers, before building six.

### Slice 3 — Serve a published snapshot (thin web tier)
- **Build:** `ordina-mind` Django + Ninja; the tables in A.6; the `publish` Nextflow step loading a snapshot; endpoints `GET /api/layers`, `GET /api/layers/{v}/coverage`, `GET /api/runs/{id}`, `POST /api/runs/{id}/seed` (Celery-dispatched walk).
- **Runs end-to-end:** published run queryable over HTTP; seeding a disease returns a ranked list.
- **Done when:** a researcher (or a test) hits `POST /seed` with a MONDO id and gets back a ranked organism list from the published multiplex.

### Slice 4 — Complete the core enrichment layers
- **Build:** `EcophysiologyLayer` (`braidworks.fetch("microbe.trait.*")` + `microbe.ecology.functional_groups` from FAPROTAX + ProTraits/Madin, merged trait vector); `MetabolicComplementarityLayer` (offline SMETANA/MICOM solver step over paired AGORA2 SBML — Nextflow, not a fetch); `CooccurrenceLayer` (compositional inference — SPIEC-EASI/SparCC, [`08`](08_decisions.md) C1); `congruence.py` (predicted-vs-observed — now buildable, since complementarity + co-occurrence both exist).
- **Done when:** the enrichment layers build/validate; recovery re-runs with a **layer-ablation** table showing each layer's contribution; the predicted-vs-observed congruence check runs.

### Slice 5 — Discovery + explanations
- **Build:** `communities.py` (MolTi); the served MultiXrank prioritisation; per-recovered-link **explain** via ablation ([`09`](09_recovery_metric.md) §9); the layer-discordance novelty query ([`04`](04_analysis_and_discovery.md)).
- **Done when:** `POST /seed` returns a ranked **and layer-explained** shortlist with coverage flags.

### Slice 6 — Web UI
- **Build:** `web/` (React + Vite + **Cytoscape.js**): browse the multiplex, seed a disease, view the explained shortlist + provenance + coverage flags, over the Ninja API.
- **Done when:** disease → mechanism-annotated shortlist works in the browser.

### Slice 7 — Flux headless + Curia
- **Build:** flesh out `ordina-flux` (A.7) beyond the Slice-0 importer — the full state machine, `ingest/normalize/promote` tasks, trigger/status API; **Curia** review screens in `web/` on top of Flux's API. Ground-up ([`08`](08_decisions.md) E1), last because nothing above depends on it.
- **Done when:** new source records flow through review into trusted `association` rows without ever touching trusted data directly.

### Critical path
`Slice 0 → 1 → 2 (⛳gate) → 3 → 4 → 5 → 6 → 7`. Everything after Slice 2 is contingent on passing the gate.
