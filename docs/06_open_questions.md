# 06 — Open questions

The honest unknowns. These are the decisions to resolve as the plan matures and as real data arrives — recorded now so they are not quietly assumed away.

> **Status:** most of these are now **resolved in [`08_decisions.md`](08_decisions.md)**. Quick map: #1→08 B4, #2→08 B2, #3→08 B1 (dual-rank), #4→08 B3, #5→08 A3, #6 (multiple testing)→[`07`](07_stack.md)/analysis (permutation + pre-registered FDR), #7→[`05`](05_validation.md) §4 firewall, #8→08 D2 (coverage audit — an action), #9→08 C1 (co-occurrence promoted to core), #10→08 D1 (MONDO), #11 still open (Flux/Curia, deferred), #12→08 A2. The original text is kept below for the reasoning trail.

## Modelling

1. **Multiplex vs heterogeneous — the final call.** [`02`](02_retes_multiplex_model.md) starts organism-centric multiplex with a bipartite disease coupling, and keeps the full heterogeneous-multilayer (Hetionet-style) as a documented pivot. The trigger for pivoting — e.g. needing pathways/metabolites as first-class prediction endpoints — must be made explicit before it happens, not drifted into.

2. **Cross-layer weight normalization.** Metabolic complementarity scores, trait Jaccards, and phylogenetic distances are not the same currency. Before any supra-adjacency walk or joint modularity, weights need a normalization scheme (within-layer z-score? quantile? rank?). The choice affects every downstream result and is currently unresolved.

3. **Taxonomic-rank mismatch.** Layers have different native ranks: metabolic reconstructions are genome/strain-level, traits are often species-level, disease findings are mixed (species→phylum). The multiplex's operating rank and the rollup rules (via `TaxonClosure`) must be chosen so that rollup doesn't hide species-level contradictions. What is the right operating rank, and when is rollup dishonest?

4. **Measured-absent vs unmeasured edges.** Sparsity from missing genomes must be distinguished from genuine dissimilarity, per the layer factory's coverage flag ([`03`](03_layer_factory_and_catalog.md)). How this propagates into community detection and random walks (which typically assume absence = no relation) is unsettled.

## Discovery and statistics

5. **What counts as "novel", and avoiding circularity.** The layer-discordance heuristic ([`04`](04_analysis_and_discovery.md)) is powerful but only meaningful if the disease layer is strictly held out as target. The operational definition of a "novel candidate" — and the guarantee that no disease signal leaks into the features — needs to be pinned down precisely.

6. **Multiple-testing burden.** A multiplex over ~hundreds–thousands of organisms generates an enormous number of candidate edges/modules. The correction strategy (FDR over what family? permutation-based empirical p-values?) is undecided and materially affects how many "discoveries" survive.

7. **Circularity with literature-derived comparators.** Using PubTator/Europe PMC (and by extension MINERVA-style KGs) both to enrich understanding and to validate risks a closed loop of literature bias ([`05`](05_validation.md)). Where exactly is the firewall?

## Data and coverage

8. **Braidworks coverage gaps.** Metabolic reconstructions, GTDB placement, and BGC catalogs all require genomes; many Disbiome taxa (uncultured, coarse-rank) may lack them. How much of the node set actually gets enriched per layer — and whether that coverage is biased toward the same well-studied organisms — is an empirical unknown that could blunt the whole approach. Needs a coverage audit early.

9. **Abundance data for the co-occurrence layer.** The most *direct* ecological layer ([`03`](03_layer_factory_and_catalog.md) §5) needs external abundance datasets (EMP/MicrobeAtlas) ORDINA doesn't yet ingest. Is it worth the ingestion cost, and when?

10. **Disease coding harmonization across sources.** Disbiome uses MedDRA; other seed sources use different disease vocabularies. Merging the disease signal across sources ([`01`](01_mind_data_foundation.md)) requires a disease-ontology mapping that doesn't yet exist here.

## Process

11. **Flux and Curia, from scratch.** Both are placeholders. Their ground-up design (async ingestion engine; review UI/workflow) is deferred but blocks the transition from "docs" to "running Mind on live Disbiome data."

12. **When is the blueprint "decent enough" to start building?** This repo is meant to iterate until the plan is solid. The exit criterion for the docs phase — and the first thing to implement after — should be agreed rather than assumed.
