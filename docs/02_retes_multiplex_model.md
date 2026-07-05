# 02 — ORDINA Retes: the multiplex model

> **This is the core research doc.** It defines what the network *is* before anything is built, because a visually attractive but semantically confused network would sink the whole project.

## Decision recorded

- **Primary framing: organism-centric multiplex.** One shared node set (canonical taxa); each layer is a distinct relation *among organisms*.
- **Guidance from the user:** "if multiplex is best, go organism-centric, else we can pivot." This doc argues the organism-centric multiplex *is* the right core, states its one real limitation honestly, resolves it, and records the pivot option (heterogeneous multilayer) if the resolution proves inadequate.

## 1. Why a multiplex, and what kind

A **multiplex network** is a set of layers that share the *same node set*, where each layer carries a different *type* of edge over those nodes [[5]](refs.md)[[6]](refs.md). This is exactly the structure we want for organisms: *Faecalibacterium prausnitzii* is one entity, and "shares metabolism with", "shares a niche with", "is phylogenetically close to", and "is co-perturbed in disease with" are four different relations over that same entity.

This is fundamentally different from a **heterogeneous / multilayer network** (à la Hetionet [[10]](refs.md)) where layers contain *different node types* (organisms, diseases, pathways, metabolites) coupled by bipartite links. Both are "layered"; only the multiplex keeps a single shared node set, which is what makes cross-layer community detection and congruence analysis clean.

**Definition (organism-centric multiplex).** Let `V` be the set of canonical taxa (nodes). A layer `α` is a weighted graph `G_α = (V, E_α, w_α)` over the *same* `V`. The multiplex is `M = {G_α}`. Every node exists in every layer (possibly isolated where data is missing); an edge means "these two organisms are related in modality `α`".

## 2. Node semantics

- **One organism = one node.** Node identity is the canonical `Taxon` (NCBI-normalized; GTDB-aligned where possible — see [`03`](03_layer_factory_and_catalog.md)). Direction of a disease effect, conflict between studies, and evidence counts are **edge/annotation properties**, never separate nodes. This fixes the current codebase's enriched/depleted node duplication.
- **Node resolution / rank — dual-rank** ([`08`](08_decisions.md) B1). Nodes are maintained at **both genus and species**. **Primary analysis runs at genus** (most robust, best coverage), with **drill-down to species** where data supports it. `TaxonClosure` handles rollup, and rollup must **preserve and surface species-level contradictions** (a genus can look neutral while its species disagree — that disagreement is a finding, not noise), never average them away. Every layer declares its native rank and an explicit genus-aggregation rule, because layers differ (metabolic models are strain/genome-level; traits are often species; disease findings are mixed).

## 3. Edge semantics

Each layer defines its own edge rule and weight (specified per layer in [`03`](03_layer_factory_and_catalog.md)). Cross-cutting requirements:

- **Weights are comparable within a layer, not across layers by default.** A metabolic-complementarity score and a trait-Jaccard are not the same currency. Cross-layer weight normalization (rank-based, z-score within layer, or quantile) is required before any supra-adjacency computation and is an explicit open question.
- **Signed / typed edges where meaningful.** The disease layer in particular is not a plain similarity — it can carry *concordant* (co-enriched or co-depleted) vs *discordant* (opposite direction) relations, and a **conflict summary** when studies disagree. Conflict is represented on the edge, never by duplicating the organism.
- **Sparsity and null edges.** Absence of an edge can mean "no relation" or "no data". Layers must distinguish *measured-absent* from *unmeasured*, or downstream analysis will confuse missing genomes with genuine dissimilarity.

## 4. The disease question, resolved honestly

**The problem.** ORDINA is a *disease* interaction atlas, yet in a pure organism-centric multiplex, disease is not a node — so there is no disease↔organism edge to draw. Pretending disease is "just another organism node" would be dishonest and would break the multiplex's single-node-set property.

**The resolution (recommended).** Treat disease at two levels:

1. **As a derived organism-layer (the "disease co-signature" layer).** Two organisms are linked in this layer when they are co-perturbed across the same disease(s) in Mind (e.g. both depleted in Crohn's across independent studies). This is a *legitimate organism–organism relation* and lives inside the multiplex like any other layer. **But it is the target we explain, not a predictor** — see [`03`](03_layer_factory_and_catalog.md) and the circularity warning in [`04`](04_analysis_and_discovery.md).
2. **As node annotations + an optional bipartite coupling for prediction.** For tasks that genuinely need disease as an endpoint (e.g. "rank organisms for disease X"), attach disease nodes as a **bipartite coupling layer** (disease–organism edges from Mind) on top of the organism multiplex. A random walk with restart over this *supra-adjacency* (organism multiplex + disease coupling) is exactly what **MultiXrank** is built for [[7]](refs.md): seed a disease, walk the enrichment layers, rank organisms. This gives us disease-endpoint prediction without polluting the multiplex's shared node set.

So: the **organism multiplex is the object of study** (community detection, congruence, module discovery), and **disease enters as (a) a derived organism-layer for structure and (b) a bipartite coupling for prediction**. This keeps the multiplex honest while still delivering disease-centric outputs.

**The pivot option (documented, not chosen).** If the bipartite-coupling approach proves too limiting — e.g. we later want pathways and metabolites as first-class endpoints for mechanistic path mining — pivot to a full **heterogeneous multilayer** (organisms, diseases, pathways, metabolites as distinct node types with typed couplings), Hetionet-style [[10]](refs.md). Trade-off: gains mechanistic path mining and multi-endpoint prediction; loses the clean single-node-set that makes multiplex modularity and cross-layer congruence straightforward, and raises the modelling/normalization burden. Recommendation: **start organism-centric multiplex; keep the heterogeneous pivot as a documented option**, re-evaluated once real layers exist.

## 5. Three graph tiers (semantic honesty)

Borrowed and kept from the prior network review, because it prevents category errors:

1. **Evidence-level multigraph** — every `EvidenceStatement` preserved; multiple studies → multiple parallel edges for the same disease–organism pair. This is the audit substrate.
2. **Summary graph** — each pair appears once per scope, with support counts, direction counts, source breakdown, and conflict metrics. This is what most analysis runs on.
3. **Projection graphs** — derived organism–organism or disease–disease graphs (e.g. the disease co-signature layer). **Clearly labelled as projections**, never presented as directly-observed biological interaction. Co-perturbation is not co-abundance and not a direct ecological interaction unless it comes from an actual abundance/co-occurrence measurement.

## 6. Null models are part of the model

No layer stands alone. Because related organisms trivially share metabolism, traits, and disease patterns, **phylogeny (GTDB) is a mandatory control layer** ([`03`](03_layer_factory_and_catalog.md)). Any claimed structure — a module, a congruent edge, a predicted association — must be shown to exceed what phylogenetic proximity and degree-preserving randomization would produce ([`05`](05_validation.md)). This requirement is baked into the model, not bolted on later.

## 7. What this buys us

With this model, the analyses in [`04`](04_analysis_and_discovery.md) become well-defined: multiplex-modularity community detection over `{G_α}`; cross-layer congruence between any two `G_α`; MultiXrank prioritization over the multiplex + disease coupling; and a layer-discordance novelty heuristic (strong in enrichment layers, absent in the disease layer). None of these are expressible on a flat single-relation graph — which is precisely the point of ORDINA over MINERVA-style KGs.
