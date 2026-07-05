# ORDINA

**Organism-Resolved Disease Interaction Network Atlas**

ORDINA turns microbiome–disease association *evidence* into an **organism-resolved multiplex network** that can be mined for structure and novel hypotheses. It does not try to be another curated association database — [Disbiome](https://disbiome.ugent.be) already fills that role well. Instead ORDINA treats curated databases as a **seed**, uses [Braidworks](https://github.com/rafaelmdc/braidworks) to **enrich** organisms with many independent biological modalities (metabolism, ecophysiology, phylogeny, chemistry…), each modality a factory-produced **layer**, and applies multiplex network analysis to surface organism modules and candidate associations that a flat association graph cannot see.

> **This repository is a docs-first research plan.** It seeds the scientific blueprint and is meant to be iterated until it is decent. No implementation lives here yet — code (Mind, Retes) migrates in later.

## Module map

| Module | Role | Status |
|---|---|---|
| **ORDINA Mind** | Knowledge base / data foundation. Disbiome-seeded, provenance-first evidence store. Today's Django app becomes Mind. | Exists (as `innovhealth_microbiome`) |
| **ORDINA Retes** | The multiplex network + analysis layer — ORDINA's net-new scientific contribution. | Design phase (these docs) |
| **ORDINA Flux** | Asynchronous ingestion / source synchronization engine. To be designed **from the ground up**. | Placeholder |
| **ORDINA Curia** | Human-in-the-loop review of candidate evidence. | Placeholder |

## The thesis, in three sentences

1. **Disbiome is a source, not a competitor** — ORDINA ingests it (plus complementary DBs) rather than re-curating microbe–disease associations by hand.
2. **Braidworks is the enrichment engine** — it connects each organism to metabolic, ecological, phylogenetic and chemical databases, and each connection becomes an independent, reproducible, provenance-tracked network **layer** produced by a layer factory.
3. **The multiplex is the contribution** — analysing organisms across many layers at once (community detection, cross-layer congruence, random-walk prioritization) yields hypotheses and structure that neither Disbiome nor a single flat knowledge graph can produce.

## Docs index

| Doc | Purpose |
|---|---|
| [`docs/00_vision_and_positioning.md`](docs/00_vision_and_positioning.md) | Why ORDINA exists; how it differs from Disbiome, MINERVA, and other KGs. |
| [`docs/01_mind_data_foundation.md`](docs/01_mind_data_foundation.md) | Mind: Disbiome as primary source, schema mapping, easier ingestion (light). |
| [`docs/02_retes_multiplex_model.md`](docs/02_retes_multiplex_model.md) | The organism-centric multiplex model; the disease-node question, resolved. |
| [`docs/03_layer_factory_and_catalog.md`](docs/03_layer_factory_and_catalog.md) | The layer factory contract and the curated, pruned layer catalog. |
| [`docs/04_analysis_and_discovery.md`](docs/04_analysis_and_discovery.md) | General ways to mine the multiplex for novel findings. |
| [`docs/05_validation.md`](docs/05_validation.md) | How to tell real signal from artifact. |
| [`docs/06_open_questions.md`](docs/06_open_questions.md) | Honest unknowns to resolve as the plan matures. |
| [`docs/refs.md`](docs/refs.md) | Bibliography. |

## Status of decisions

The scope, network model, and layer set are recorded at the top of each doc. The current headline decisions: **docs-only repo for now**; **organism-centric multiplex** as the primary framing (with a documented heterogeneous-multilayer pivot); and a **curated four-layer enrichment set** (metabolic, phylogeny-as-control, ecophysiology, BGCs) after an explicit relevance pass that dropped redundant candidates. See [`docs/03`](docs/03_layer_factory_and_catalog.md) for the reasoning behind every inclusion and cut.
