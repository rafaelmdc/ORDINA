# 04 — Analysis and discovery

> **Scope note.** Kept deliberately general. The exact algorithms, parameters, and thresholds can only be fixed once real layers exist and we see their density and noise. This doc commits to a *solid, honest strategy* and names the established methods it will draw on — not a tuned pipeline.

The organizing question: **what can a multiplex of organisms tell us that the raw association list cannot?** Four families of analysis, each a *hypothesis generator*, not a conclusion.

> **Two things every analysis below assumes.** (1) The node set is the *union* of all taxa with a per-layer coverage mask ([`08`](08_decisions.md) B5), so each analysis runs on a layer's **measured-induced subgraph** — an organism with no data in a layer is *unmeasured*, never treated as dissimilar. (2) Every finding is checked against **two** nulls, not one: the **phylogeny null** (related organisms behave alike) *and* the **study-effort null** (well-studied organisms show up everywhere — the bias the coverage audit confirmed). See the recovery metric ([`09`](09_recovery_metric.md)) for how both are operationalized.

## 1. Cross-layer module discovery (community detection)

**Goal:** find groups of organisms that hang together *across multiple independent layers* — e.g. a set that is simultaneously metabolically complementary, niche-overlapping, and co-perturbed in a disease.

**Approach:** multiplex community detection that optimizes structure over all layers jointly, rather than clustering each layer separately and intersecting.
- **MolTi** — multiplex-modularity optimization (adapted Louvain), which handles weighted edges and weighted layers and empirically finds better-defined functional modules than aggregating or consensus-clustering single layers, especially when layers are incomplete/heterogeneous in density — exactly our situation [[6]](refs.md).
- **Multilayer Infomap / generalized-Louvain** as alternative community models with different inductive biases (flow-based vs modularity-based) [[5]](refs.md).

**Directed / signed layers are handled per [`08`](08_decisions.md) B6.** MolTi and standard multiplex modularity assume **undirected, unsigned, positive** layers, but some of ours are not (metabolic *exchange* is directed A→B; the disease co-signature and co-occurrence layers are *signed* — concordant/discordant, co-presence/co-exclusion). B6 settles it: unsigned/undirected layers use MolTi as-is; **signed** layers use a **signed method** — concretely, split each into positive/negative sub-layers and run `leidenalg.optimise_partition_multiplex` with `layer_weights=[+1, −1]` (signed modularity Q⁺ − Q⁻), so a `+` edge groups two organisms together and a `−` edge pushes them apart (co-exclusion is real anti-grouping information, not noise); **directed** layers use a **flow-based, direction-respecting method** (multilayer Infomap) or an explicitly-stated symmetrization. The raw directed/signed edges are always retained — they also drive the random-walk (which travels positive, direction-respecting edges; a `−` edge is a separate penalty signal, not a step) and congruence analyses even where a modularity run discards them.

**What a result means:** a module coherent across layers is a candidate *functional/ecological guild*. Modules that are *also* disease-enriched are candidate disease-relevant consortia.

**Honesty guard:** report which layers drive each module, and test every module against the phylogeny null *and* the study-effort null (§ [`05`](05_validation.md), [`09`](09_recovery_metric.md)). A "module" that is just a clade — or just the well-studied organisms clumping together — is not a discovery.

## 2. Cross-layer congruence and redundancy

**Goal:** understand the *layers themselves* — which agree, which carry independent signal.

**Approach:** pairwise layer similarity (edge-overlap, correlation of weight matrices, or mutual information of partitions) and comparison against the phylogeny layer. Identify:
- **Redundant layers** (highly congruent with phylogeny or each other) → candidates to down-weight or merge.
- **Orthogonal layers** (independent signal) → the valuable ones; disagreements between them are where interesting biology hides.

**Why it matters:** it is the internal check that the multiplex is more than one signal wearing several hats. If every enrichment layer collapses onto phylogeny, ORDINA reduces to a phylogenetic tree and we should say so.

## 3. Link prediction / prioritization (multilayer random walk)

**Goal:** rank organisms for a disease (or organisms for an organism) using the whole multiplex at once.

**Approach:** **Random Walk with Restart on the multilayer** via **MultiXrank** [[7]](refs.md): seed a disease node (through the bipartite disease coupling of [`02`](02_retes_multiplex_model.md)), walk across the enrichment layers, and read out proximity scores over all organisms. Scores can also feed a supervised classifier trained on older associations and evaluated on newer ones — a design MultiXrank explicitly supports.

**Outputs:** ranked candidate disease–organism associations; disease "diffusion profiles" usable as disease signatures for disease–disease similarity.

## 4. Layer-discordance novelty heuristic

**Goal:** the sharpest ORDINA-specific discovery mode — find associations the literature hasn't made yet.

**Heuristic:** look for organisms (or whole modules) that are **strongly connected in enrichment layers** (metabolic / ecophysiology / BGC) to organisms known to be disease-associated, **but are themselves absent from the disease layer**. Such an organism is "guilty by mechanistic association" — a candidate undiscovered disease link, motivated by a concrete mechanism (shared pathway, niche, metabolite exchange), not by co-mention.

**Why this is the payoff:** it is exactly the inference a flat association graph or a co-mention KG *cannot* make, because it requires orthogonal mechanistic layers that the disease signal is silent on.

**Critical circularity guard:** *for this finding*, the disease layer must be held out as the target — none of the disease signal may be among the inputs used to generate these candidates (see [`03`](03_layer_factory_and_catalog.md) §3.0). Otherwise we would "predict" what we fed in. This is the specific application of the general rule in [`08`](08_decisions.md) A4: the disease data can be an input in *other* findings, but never inside the single test where it is the thing being predicted ("don't grade your own homework").

## 5. Keystone / centrality across layers

**Goal:** identify organisms whose position across layers marks them as structurally important (hubs, cross-layer connectors, module bridges) — candidate keystone species.

**Approach:** multiplex centrality measures (versatility / multiplex PageRank) rather than per-layer degree, so importance reflects the organism's role across modalities. Framed as hypothesis: structural centrality ≠ proven biological keystone-ness; it prioritizes candidates for the validation and experimental follow-up in [`05`](05_validation.md).

## 6. Framing for every output

Every analysis above emits **ranked, mechanistically-annotated hypotheses**, each carrying: the layers that support it, its behaviour under the phylogeny *and* study-effort nulls, and a provenance trail to the source evidence. None is presented as an established fact. The discovery engine's job is to hand a microbiome researcher a short, well-motivated, testable shortlist — and to be honest about the uncertainty on each item.
