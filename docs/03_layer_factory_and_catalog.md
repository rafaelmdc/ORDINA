# 03 — The layer factory and layer catalog

> The user's requirement: *"a layer should be the result of a factory"* — so new modalities can be added later without redesigning the network. This doc defines that factory contract, then catalogs the layers **after an explicit relevance pass** that pruned redundant candidates rather than accumulating them.

## 1. The layer factory contract

A **layer** is not just "some edges". It is a reproducible object produced by a factory that must declare all of:

| Element | What it specifies |
|---|---|
| **Node mapping** | How the layer's native entities map onto canonical taxa `V` (and at which rank; how rollup is handled). |
| **Braidworks path** | The concrete strand→strand route through Braidworks weavers that fetches the raw data (e.g. `taxon → genome → reactions`). New weavers are built on demand. |
| **Edge-construction rule** | When two organisms get an edge (shared feature threshold, complementarity score, distance cutoff…). |
| **Weight / similarity metric** | The numeric edge weight and its meaning (Jaccard, complementarity index, 1−distance…). |
| **Provenance** | Source DB, version/snapshot, and per-edge traceability. |
| **Null / baseline model** | How to tell this layer's structure from phylogenetic/degree artifact ([`05`](05_validation.md)). |
| **Coverage flag** | For each node: measured-present / measured-absent / unmeasured (so sparsity isn't mistaken for dissimilarity). |

Because every layer implements the same contract, the multiplex is open-ended: adding a layer = registering one more factory output over the same `V`.

### Braidworks as the substrate

[Braidworks](https://github.com/rafaelmdc/braidworks) federates biological databases via "weavers" (per-source wrappers exposing `resolve_* / list_* / describe_*` capabilities) and auto-plans multi-hop routes between the data you *have* (a taxon) and the data you *want* (its reactions, traits, BGCs). It already ships weavers for **Disbiome, Reactome, STRING, QuickGO, BacDive, NCBI Taxonomy, UniProt, PDBe, AlphaFold**, and **new weavers can be built on demand** — so the catalog below is not limited to existing weavers.

## 2. The relevance pass (guiding rule)

A candidate layer earns a place **only if** it:

1. yields a genuine **organism–organism** edge over the shared node set `V`, *and*
2. adds signal **not already captured** by another layer or by phylogeny.

Applying this rule deliberately *shrank* the catalog. The cuts are documented (§4) so the decisions are auditable rather than silent.

## 3. Curated layer set

### 3.0 Target/observation layer — Disease co-signature
- **Source:** Mind (Disbiome + GMrepo/gutMDisorder/MASI). Not a new weaver — internal to Mind.
- **Edge:** two organisms are linked when co-perturbed across the same disease(s) (co-enriched / co-depleted); concordant vs discordant is edge-typed; conflict summarized on the edge.
- **Special role — this is the *target*, not a predictor.** It is the signal the enrichment layers exist to explain and extend. **Using it to "discover" disease associations would be circular** ([`04`](04_analysis_and_discovery.md)). It defines the questions.
- **Caveat:** it is a *projection* (co-perturbation ≠ co-abundance ≠ ecological interaction).

### Enrichment layers, ranked by relevance

### 3.1 Metabolic — **top priority**
- **Sources (new weavers):** genome-scale metabolic reconstructions — **KEGG**, **MetaCyc**, and especially **AGORA / Virtual Metabolic Human (VMH)** [[11]](refs.md), which provides curated gut-microbe reconstructions ready for community modelling. **HMDB** [[12]](refs.md) feeds the metabolite side.
- **Edges (two flavours over the same node set):**
  1. *Function-repertoire sharing* — organisms sharing pathways/modules (Jaccard over reaction/module sets).
  2. *Metabolic complementarity / competition / exchange* — predicted cross-feeding or resource competition from paired reconstructions (e.g. SMETANA-style metabolic-interaction potential, or MICOM-style community flux) [[13]](refs.md).
- **Why #1:** this is the most *novel* and most *ecologically mechanistic* organism–organism signal — it is what actually drives microbial community structure, not just similarity. It also subsumes the old "metabolite exchange" future layer.
- **Caveats:** requires genomes/reconstructions (coverage-limited for uncultured taxa); complementarity predictions are models, not measurements; strain/genome-level source vs. species-level nodes needs rollup.

### 3.2 Phylogeny — **GTDB — the control layer (essential, but not a discovery layer)**
- **Source (new weaver):** **GTDB** [[14]](refs.md) — genome-based taxonomy with quantitative marker-gene distances (supersedes NCBI/SILVA lineage-depth as a distance).
- **Edge:** organism–organism phylogenetic proximity (1 − normalized distance).
- **Role:** the **mandatory null/confounder model**. Related taxa trivially share metabolism, traits, and disease patterns; every other layer's structure must be shown to *exceed* what phylogeny predicts. It is a baseline to beat, not a source of novel hypotheses.
- **Caveat:** NCBI stays only as the ID-normalization backbone in Mind; GTDB is the phylogeny layer.

### 3.3 Ecophysiology / traits — **merged niche layer**
- **Sources:** **BacDive** [[15]](refs.md) (existing weaver) **+ ProTraits** [[16]](refs.md) **+ Madin et al. trait DB** [[17]](refs.md), combined into one layer.
- **Edge:** niche/trait overlap (oxygen tolerance, habitat, pH/temperature optima, motility, gram stain, sporulation, …) — weighted similarity over a harmonized trait vector.
- **Why merged:** BacDive, ProTraits, and Madin are the *same modality* (microbial phenotype); keeping them separate would be three redundant layers. Merged, they maximize coverage.
- **Caveat:** trait data is sparse and biased toward cultured organisms; many gut anaerobes are under-covered. Flagged sparse.

### 3.4 Secondary metabolites / BGCs — **exploratory, second wave**
- **Sources (new weavers):** **antiSMASH** / **gutSMASH** [[18]](refs.md) biosynthetic gene cluster catalogs.
- **Edge:** organisms producing similar or complementary secondary metabolites (antibiotics, siderophores, bacteriocins) → potential chemically-mediated interaction.
- **Why kept but deferred:** genuinely novel organism–organism signal (chemical warfare/cooperation), but genome-dependent and sparse. Develop **after** the top three layers are working.

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

- **Abundance co-occurrence** — from real abundance datasets (**Earth Microbiome Project**, **MicrobeAtlas**) [[20]](refs.md). Arguably the *most direct* ecological organism–organism signal (co-occurrence across many samples), more direct than trait similarity — but it needs external abundance data ORDINA doesn't yet ingest. **Flagged high-value-pending.**
- **Host-interaction** — organisms sharing host-cell/immune interaction partners.
- **Strain resolution** — sub-species layers where strain-level genomes exist.

Each, if promoted, must satisfy the same factory contract (§1) and the relevance rule (§2).

## 6. Summary

Fewer, sharper layers, no redundant ones: **disease co-signature** (target), **metabolic** (top predictor), **phylogeny/GTDB** (control), **ecophysiology** (niche), **BGCs** (exploratory). Everything else was dropped, folded, demoted, or reclassified — on the record.
