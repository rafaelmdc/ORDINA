# 03 — The layer factory and layer catalog

> The user's requirement: *"a layer should be the result of a factory"* — so new modalities can be added later without redesigning the network. This doc defines that factory contract, then catalogs the layers **after an explicit relevance pass** that pruned redundant candidates rather than accumulating them.

## 1. The layer factory contract

A **layer** is not just "some edges". It is a reproducible object produced by a factory that must declare all of:

| Element | What it specifies |
|---|---|
| **Node mapping** | How the layer's native entities map onto canonical taxa `V`. |
| **Native rank + aggregation rule** | The rank the layer's data natively lives at (genome/strain, species, mixed), and the explicit rule for aggregating it to the **genus** primary-analysis rank while preserving species-level detail. Mandatory under the dual-rank decision ([`08`](08_decisions.md) B1). |
| **Braidworks fetch** | The concrete `braidworks.fetch(want, ids)` call that fetches the raw per-organism data — `want` is the target strand-type(s) (e.g. `"microbe.metabolism.reactions"`), `ids` the taxa. Braidworks routes taxon→genome→reactions internally. New weaver capabilities are built on demand. |
| **Edge-construction rule** | When two organisms get an edge (shared feature threshold, complementarity score, distance cutoff…). |
| **Weight / similarity metric** | The numeric edge weight and its meaning (Jaccard, complementarity index, 1−distance…). |
| **Provenance** | Source DB, version/snapshot, and per-edge traceability. |
| **Null / baseline model** | How to tell this layer's structure from phylogenetic/degree artifact ([`05`](05_validation.md)). |
| **Coverage flag** | For each node: measured-present / measured-absent / unmeasured (so sparsity isn't mistaken for dissimilarity). |

Because every layer implements the same contract, the multiplex is open-ended: adding a layer = registering one more factory output over the same `V`.

### Braidworks as the substrate

[Braidworks](https://github.com/rafaelmdc/braidworks) is the project's data-access library: per-source **weavers** (each declaring, in typed terms, the strand-types it *consumes* and *produces*) plus automatic multi-hop routing between the data you *have* (a taxon) and the data you *want* (its reactions, traits, distances). ORDINA calls it generically through the **`braidworks.fetch(want, ids)`** facade — a thin convenience over Braidworks' `plan/execute` core that batch-resolves a target strand-type for a list of ids and reports which ids came back empty (the coverage-gap signal we need). ORDINA never touches external databases directly.

It already ships weavers for **Disbiome, NCBI Taxonomy, GTDB, AGORA2, BacDive, FAPROTAX, Reactome, STRING, QuickGO, UniProt, PDBe, AlphaFold, Wikidata, Wikipedia**, and **new weavers/capabilities are built on demand** — so the catalog below is not limited to existing sources. **Two honesty notes** that shape the layer specs: the GTDB weaver's taxonomy + lineage was extended with a new **`gtdb.tree.rootpath`** capability (per-entity tree placement; pairwise patristic distance reduced client-side, §3.3), and the AGORA2 weaver produces reaction *repertoires* but not community-flux *complementarity* (which is an offline solver step, not a fetch — §3.1).

## 1a. The concrete contract — what a factory actually outputs (buildable spec)

The table above is the *idea*; this section is the *build spec*, so an engineer can implement a layer without guessing. Three concrete objects: the **node universe**, the **built layer**, and the **factory** that turns one into the other. (Field types are illustrative — the point is the shape and the rules, not the exact library.)

### The node universe `V` (shared, versioned)

Every layer is built against **one frozen snapshot of the node set** — the *union* of all Disbiome taxa at both ranks ([`08`](08_decisions.md) B5). Freezing it (and hashing it) is what makes two layers stackable and a build reproducible.

```
V-snapshot
  version            content hash of the node set + build date   (e.g. "V-2026.07-a1b2c3")
  sources            Disbiome snapshot id + NCBI taxonomy version used to resolve ranks
  nodes[]            one row per node:
    taxid            NCBI taxid
    rank             "genus" | "species"
    canonical_name   NCBI scientific name
    parent_genus     the genus taxid this species rolls up to (null for genus rows)
    in_disbiome      true (all V nodes come from Disbiome in iteration 1)
```

### The built layer (what a factory emits)

A built layer is a small, self-describing, content-addressed bundle — **a manifest + an edge list + a coverage list**.

```
manifest.json
  layer_id          "metabolic.complementarity", "phylogeny.gtdb", …
  layer_version     the deterministic ADDRESS of this layer = hash of its pinned inputs
                    (built_on_V + source snapshot ids + params + random seed + code version).
                    See "reproducibility" note below — this is an input-hash, not a hash of
                    possibly-nondeterministic output bytes.
  built_on_V        the V-snapshot version it was built against   (must match to stack)
  native_rank       "genome" | "strain" | "species" | "mixed"
  aggregation_rule  how native rank was rolled to genus (short id + description) — mandatory (B1)
  directed          false for symmetric layers (similarity); true for directed ones (e.g. metabolic
                    exchange, where A→B feeding ≠ B→A) — tells the assembler to build an asymmetric matrix
  edge_semantics    "similarity" | "directed_exchange" | "signed_cosignature"
                    — how to read src/dst order and the sign column
  sources[]         [{db, version_or_snapshot, url}]
  braidworks_fetch  the want strand-type(s) + weaver versions that fetched the data
                    (e.g. want="microbe.metabolism.reactions" via the agora weaver)
  edge_rule         one line: when two organisms get an edge
  weight_metric     name + meaning (e.g. "SMETANA complementarity, 0–1, higher = more cross-feeding")
  normalization     {method: "rank" (default) | "quantile", params, applied: "at_build"}   (B2)
                    — rank-to-[0,1] over MEASURED edges only; for signed layers this normalizes the
                    magnitude and the sign column is kept separately. (z-score/min-max rejected in B2.)
  null_model        {type: "phylogeny"|"degree_preserving"|…, params}   (how to test vs artifact, doc 05)
  seed              the RNG seed for any stochastic step (community modelling, sampling) — recorded so runs reproduce
  determinism       "exact" for deterministic layers (phylogeny, repertoire-sharing) |
                    "seeded_tolerant" for layers that call stochastic/platform-sensitive tools
  build             {date, code_version, n_edges, n_measured_nodes, output_check}
                    output_check = for "exact" layers, a content digest asserted bitwise on rebuild;
                    for "seeded_tolerant" layers, a NUMERIC fingerprint (sorted w_norm quantiles +
                    top-N edge weights) compared within a recorded tolerance ε — you cannot put a
                    tolerance on a hash, so the tolerant check must compare numbers, not a digest.

edges                one row per organism–organism edge, per rank:
  rank               "genus" | "species"
  src_taxid, dst_taxid   order is meaningful only when manifest.directed is true
  w_raw              the layer's native weight (kept as provenance)
  w_norm             the within-layer normalized weight in [0,1] (B2) — what analysis uses
  sign               +1 | -1 | null  — for signed layers (e.g. disease co-signature: concordant vs
                     discordant; co-occurrence: co-presence vs co-exclusion). null for plain similarity layers.
  evidence_ref       pointer back to the source facts that produced this edge (provenance)

coverage             one row per node in V, per rank — the three-state mask (B3/B5):
  rank, taxid
  state              "present"          node measured AND has ≥1 edge in this layer
                     "measured_absent"  node measured, but genuinely no edge passed threshold (a real "no relation")
                     "unmeasured"       no data for this node in this layer → isolated, treated as UNKNOWN, never as zero-similarity
```

The **coverage list is not optional and not derived from the edges** — a node can be `measured_absent` (we looked, there's no relation) or `unmeasured` (we never had data), and those look identical in an edge list but must never be treated the same downstream. This is the field that makes the union node set honest.

### The factory interface

```
LayerFactory
  layer_id
  declare()  -> manifest metadata only, no data
               (sources, native_rank, aggregation_rule, braidworks_fetch, null_model)
               — lets us list/plan layers before building them.
  build(V_snapshot, source_snapshots) -> BuiltLayer
               pipeline, in order:
                 1. fetch        — call braidworks.fetch(want, ids) to pull raw per-organism data
                                   (the phylogeny layer is the one exception: its want,
                                   gtdb.tree.rootpath, reduced pairwise client-side — §3.3)
                 2. map_to_V     — resolve source entities onto taxids in V (drop anything not in V)
                 3. construct    — apply edge_rule to get raw organism–organism edges
                 4. weight       — assign w_raw
                 5. aggregate    — roll native rank up to genus per aggregation_rule (keep species too)
                 6. normalize    — w_raw -> w_norm in [0,1] within the layer (B2)
                 7. coverage     — label every V node present / measured_absent / unmeasured
                 8. provenance   — attach evidence_ref + sources + fetch(want) + hashes
  validate(BuiltLayer) -> must pass:
                 - every node in V has exactly one coverage state (no missing, no dupes)
                 - no edge references a taxid outside V
                 - all w_norm in [0,1]; sign in {+1,-1,null}; directed flag consistent with edge_semantics
                 - a rebuild from the same pinned inputs + seed passes the output_check:
                   "exact" layers reproduce the digest bitwise; "seeded_tolerant" layers reproduce
                   the numeric fingerprint within tolerance ε (see note)
```

**Reproducibility, honestly.** `layer_version` is a hash of the **pinned inputs** (V-version, source snapshot ids, params, RNG seed, code version). This is the deterministic **address** we stack by — but note it is an *input* hash, so "a rebuild reproduces `layer_version`" is trivially true and proves nothing about the output; it is not the determinism check. The determinism check is the separate `build.output_check`, and it splits by layer type:

- **Deterministic layers** (phylogeny patristic distance, metabolic repertoire-sharing Jaccard) — `determinism: "exact"`. A rebuild must reproduce a **content digest bitwise**; any drift is a bug.
- **Stochastic / platform-sensitive layers** (community metabolic modelling, MolTi randomization) — `determinism: "seeded_tolerant"`. These are **seeded** (stack doc [`07`](07_stack.md) §9), but seeding does not guarantee identical bytes across platforms, so the check compares a **numeric fingerprint** (sorted `w_norm` quantiles + top-N edge weights) within a recorded tolerance ε. **You cannot put a tolerance on a hash** — the tolerant check must compare numbers, which is why `output_check` is a fingerprint, not a digest, for these layers.

Determinism lives in the pinned inputs; the output check is what actually catches a broken rebuild, and it is honest about which layers can promise exact bytes and which can only promise "numerically the same within ε."

### Where it lives (storage / snapshot format)

Aligned with the stack ([`07`](07_stack.md)): the **manifest + coverage** go in **PostgreSQL** (queryable — "which layers measured this taxon?"), the **edge list** is stored as **Parquet / a sparse matrix** in object storage and loaded into `scipy.sparse` for the walks and community detection. A layer is addressed by `(layer_id, layer_version)`; the multiplex for a run is just *"these layer_versions, all built_on the same V-snapshot."* That tuple is the whole reproducibility contract — anyone can re-fetch the exact network a result came from.

## 2. The relevance pass (guiding rule)

A candidate layer earns a place **only if** it:

1. yields a genuine **organism–organism** edge over the shared node set `V`, *and*
2. adds signal **not already captured** by another layer or by phylogeny.

Applying this rule deliberately *shrank* the catalog. The cuts are documented (§4) so the decisions are auditable rather than silent.

## 3. Curated layer set

### 3.0 Target/observation layer — Disease co-signature
- **Source:** Mind (Disbiome + GMrepo/gutMDisorder/MASI). Not a new connector — internal to Mind.
- **Edge:** two organisms are linked when co-perturbed across the same disease(s) (co-enriched / co-depleted); concordant vs discordant is edge-typed; conflict summarized on the edge.
- **Special role — this is the *target*, not a predictor.** It is the signal the enrichment layers exist to explain and extend. **Using it to "discover" disease associations would be circular** ([`04`](04_analysis_and_discovery.md)). It defines the questions.
- **Caveat:** it is a *projection* (co-perturbation ≠ co-abundance ≠ ecological interaction).

### Enrichment layers, ranked by relevance

### 3.1 Metabolic — **top priority, and it is TWO layers, not one**
The metabolic signal comes in two forms with very different build costs and coverage, so they are **two distinct layers** (each its own factory, manifest, coverage mask). Conflating them hid a real dependency: the "headline" congruence result (§3.2, [`05`](05_validation.md) §4b) needs the *harder* one.

- **`metabolic.repertoire` — function-repertoire sharing (feasible now; this is the gate layer).**
  - **Source:** **AGORA2 / Virtual Metabolic Human (VMH)** [[11]](refs.md) reconstructions, fetched via `braidworks.fetch("microbe.metabolism.reactions", ids)` (the existing agora weaver). KEGG/MetaCyc are alternative repertoire sources; **HMDB** [[12]](refs.md) feeds the metabolite side.
  - **Edge:** Jaccard over each organism's reaction/module set. Deterministic (`output_check: exact`).
  - **Role:** cheap, buildable today, and it is the metabolic layer used at the **Slice-2 go/no-go gate** ([`10`](10_architecture_and_roadmap.md)).

- **`metabolic.complementarity` — predicted cross-feeding / competition / exchange (second wave, NOT a fetch).**
  - **Source:** paired AGORA2 SBML reconstructions run through **community-flux modelling** — SMETANA-style metabolic-interaction potential or MICOM-style community flux [[13]](refs.md). This is **not** a `braidworks.fetch` — it is an offline **Nextflow solver step** over pairs of genome-scale models ([`07`](07_stack.md) §8), heavy and coverage-limited.
  - **Edge:** predicted directed exchange / complementarity score; `directed: true`; `determinism: seeded_tolerant`.
  - **Why it still earns its place:** it is the most *ecologically mechanistic* organism–organism signal — what actually drives community structure — and it *predicts* interaction that the co-occurrence layer *observes* (§3.2). It also subsumes the old "metabolite exchange" future layer.

- **Caveats (both):** require genomes/reconstructions (coverage-limited for uncultured taxa — the D2 audit measures this); complementarity predictions are models, not measurements; strain/genome-level source vs. species/genus nodes needs the declared rollup.

### 3.2 Abundance co-occurrence — **observed ecology (core; promoted per [`08`](08_decisions.md) C1)**
- **Sources (new connectors / ingestion):** human-gut-relevant abundance profiles — **`curatedMetagenomicData`** and **GMrepo** abundance — prioritized over environmental **Earth Microbiome Project**; **MicrobeAtlas** for breadth [[20]](refs.md).
- **Edge:** inferred co-occurrence / co-exclusion between organisms across samples.
- **Inference (correctness-critical):** abundances are **compositional**, so naive correlation is **forbidden**. Use **SPIEC-EASI**, **SparCC**, or **FlashWeave** [[22]](refs.md).
- **Why core, and the key synergy:** this layer *observes* interaction, whereas `metabolic.complementarity` (§3.1) *predicts* it. **Congruence between predicted and observed interaction is a headline cross-layer analysis and a strong internal validation signal** ([`05`](05_validation.md)) — neither layer alone provides it. **Dependency to be honest about:** this headline needs `metabolic.complementarity` (the solver-based second-wave layer) *and* this co-occurrence layer, so it is an **iteration-1.5 result**, not something the Slice-2 gate (which runs on `metabolic.repertoire`) can show.
- **Caveat:** co-occurrence ≠ causation; sample-set composition and study batch effects confound; it is a genuine ecological signal but still a projection.

### 3.3 Phylogeny — **GTDB — the control layer (essential, but not a discovery layer)**
- **Source + the new capability it requires:** **GTDB** [[14]](refs.md). The existing GTDB weaver returns taxonomy + lineage only, so the phylogeny layer needs a **new Braidworks capability** that loads the GTDB **bac120/ar53 reference tree** (Newick) and yields the **patristic (cophenetic) distance** — the sum of branch lengths on the path between two representative-genome leaves. This is a *genuine genome-phylogeny distance*, which is why GTDB genuinely **supersedes** NCBI/SILVA lineage-depth (counting shared rank levels); a lineage-overlap proxy would *not*, and is only the fallback if the tree integration slips (GTDB's per-taxon **RED** values are the interim, still tree-derived). Building this capability is an explicit **Slice-1 prerequisite** ([`10`](10_architecture_and_roadmap.md)).
  - **Built as (Slice 1):** because Braidworks resolves strictly **per entity** (never per pair), the capability is `describe_gtdb_tree_placement` → **`gtdb.tree.rootpath`**: each organism → its leaf's root-to-leaf path (`[node_id, cumulative_depth]`), a pure, cacheable per-id value. The **pairwise** patristic reduction is `gtdb_weaver.cophenetic(path_a, path_b)` (deepest shared node) — authored once beside the tree, called by this layer. This keeps the pairwise math in the layer's `aggregation_rule` (below) without a pairwise shape in Braidworks core. See [`10`](10_architecture_and_roadmap.md) A.5.
- **Edge:** organism–organism phylogenetic proximity `w_raw = 1 − distance/tree_diameter` (Slice 1 normalizes by the max distance *in the measured set*, then rank-maps to [0,1] — monotonic in distance, so the normalizer choice doesn't change the ranking). Deterministic (`output_check: exact`).
- **Rank rule (B1):** species → its GTDB representative-genome leaf; genus → mean (or min) patristic distance over the two genera's child-species leaves — declared in `aggregation_rule` (implemented: `aggregation ∈ {mean, min}`).
- **Role:** the **mandatory null/confounder model**. Related taxa trivially share metabolism, traits, and disease patterns; every other layer's structure must be shown to *exceed* what phylogeny predicts. It is a baseline to beat, not a source of novel hypotheses.
- **Caveat:** NCBI stays only as the ID-normalization backbone in Mind; GTDB is the phylogeny layer.

### 3.4 Ecophysiology / traits — **merged niche layer**
- **Sources:** **BacDive** [[15]](refs.md) (existing weaver, `microbe.trait.*`) **+ ProTraits** [[16]](refs.md) **+ Madin et al. trait DB** [[17]](refs.md), combined into one layer. **FAPROTAX** (existing weaver, `microbe.ecology.functional_groups`) is a **free coverage win**: it maps a clade to ecological/metabolic functional groups (methanotrophy, nitrate reduction, fermentation, …) and is already in Braidworks, so it can seed/augment the harmonized trait vector at no new-connector cost.
- **Edge:** niche/trait overlap (oxygen tolerance, habitat, pH/temperature optima, motility, gram stain, sporulation, functional groups, …) — weighted similarity over a harmonized trait vector.
- **Why merged:** BacDive, ProTraits, Madin, and FAPROTAX are the *same modality* (microbial phenotype/ecology); keeping them separate would be redundant layers. Merged, they maximize coverage.
- **Caveat:** trait data is sparse and biased toward cultured organisms; many gut anaerobes are under-covered. Flagged sparse. (FAPROTAX is clade-inferred, so it is broad but coarse — useful for coverage, weak as fine discrimination.)

### 3.5 Secondary metabolites / BGCs — **exploratory, second wave**
- **Sources (new connectors):** **antiSMASH** / **gutSMASH** [[18]](refs.md) biosynthetic gene cluster catalogs.
- **Edge:** organisms producing similar or complementary secondary metabolites (antibiotics, siderophores, bacteriocins) → potential chemically-mediated interaction.
- **Why kept but deferred:** genuinely novel organism–organism signal (chemical warfare/cooperation), but genome-dependent and sparse. Develop **after** the core enrichment layers (metabolic, co-occurrence, phylogeny, ecophysiology) are working.

## 4. Cut or reclassified in this pass (with rationale)

Documented so the decisions are auditable and reversible:

| Candidate | Verdict | Rationale |
|---|---|---|
| **STRING PPI** [[19]](refs.md) | **DROP** | Protein interactions are *within*-organism; they don't define a clean organism–organism edge in an organism-centric multiplex, and they duplicate the metabolic/functional signal. Would only return under the heterogeneous-multilayer pivot. |
| **Reactome** as a microbial metabolic layer | **DROP** | Human-pathway-centric; the wrong substrate for microbes. Superseded by KEGG/MetaCyc/AGORA. |
| **QuickGO GO-term overlap** | **FOLD into metabolic** | Largely restates functional similarity and is heavily phylogeny-driven; not worth a standalone layer. |
| **NCBI / SILVA distance** | **DEMOTE** | Kept only as ID normalization inside Mind; GTDB is the phylogeny layer. |
| **GMrepo / gutMDisorder / MASI** | **RECLASSIFY** | Not organism–organism layers — they are Mind seed sources + cross-source validation ([`01`](01_mind_data_foundation.md), [`05`](05_validation.md)). |
| **HMDB** | **RECLASSIFY** | A metabolite resource; feeds the metabolic layer rather than being its own organism–organism layer. |

## 5. Genuinely-future layers (sketched only)

- **Host-interaction** — organisms sharing host-cell/immune interaction partners.
- **Strain resolution** — sub-species layers where strain-level genomes exist.

Each, if promoted, must satisfy the same factory contract (§1) and the relevance rule (§2).

## 6. Summary

Fewer, sharper layers, no redundant ones: **disease co-signature** (target), **metabolic.repertoire** (function-sharing, feasible now, the gate layer) and **metabolic.complementarity** (predicted interaction, solver-based second wave), **abundance co-occurrence** (observed interaction — the predicted-vs-observed congruence between complementarity and co-occurrence is the headline result), **phylogeny/GTDB** (control, needs the new `gtdb.patristic_distance` capability), **ecophysiology** (niche, now including FAPROTAX), **BGCs** (exploratory). Everything else was dropped, folded, demoted, or reclassified — on the record. See [`08`](08_decisions.md) for the decisions that shaped this set.
