# 01 — ORDINA Mind: the data foundation

> **Scope note.** Mind is deliberately *not* the main focus of this pivot. The point is to stop reinventing curation and lean on existing sources. This doc fixes the data foundation and the ingestion *principles*; it does **not** design the ingestion engine (that is Flux, built ground-up later). Detail here stays light on purpose.

## Role

**ORDINA Mind** is the knowledge base: the provenance-tracked store of microbe–disease association evidence that seeds the multiplex. Today's Django application (`innovhealth_microbiome`) becomes Mind; its schema is a good starting substrate and is kept.

## Primary source: Disbiome

Disbiome [[1]](refs.md) is the primary seed, not a competitor to reproduce. Its model is **Experiment-centric** — each record is one measured microbiota difference between a patient group and a control, carrying:

- **Publication** (with PubMed ID) and a 16-item study-quality assessment;
- **Organism**, linked to **NCBI** and **SILVA** taxonomy;
- **Disease**, coded with **MedDRA** (Preferred-Term level, within the 5-level LLT→PT→HLT→HLGT→SOC hierarchy);
- **Sample type** (feces, biopsy, skin swab, …; ~50 types);
- **Detection method** (qPCR, DGGE, 16S/NGS, shotgun, …; >25 methods);
- **Outcome**: qualitative direction (organism *elevated* or *reduced* in patients) plus quantitative value/ratio where available.

Disbiome exposes a JSON API and refreshes on a manual cadence, so ORDINA can pull it programmatically rather than hand-entering studies.

### Complementary seed sources

To enlarge and cross-check the disease signal (these feed Mind and validation, **not** the multiplex layers — see [`03`](03_layer_factory_and_catalog.md)):

- **GMrepo** [[8]](refs.md) — curated human gut microbiome runs with disease metadata;
- **gutMDisorder** [[9]](refs.md) — curated microbiota–disorder / intervention associations;
- **MASI** and similar microbiota–substance/intervention resources.

Using more than one curated source lets ORDINA measure **cross-source concordance** for each association — a validation signal Disbiome alone cannot provide.

### Disease vocabulary: MONDO

Sources use different disease vocabularies (Disbiome uses MedDRA). Mind **standardizes all of them onto MONDO** ([`08`](08_decisions.md) D1), mapping MedDRA and the other sources' codes into MONDO while **keeping source-native codes as provenance**. MONDO's cross-references (MedDRA/DO/EFO/OMIM) make the mapping tractable, and a common disease space is what makes cross-source concordance meaningful.

### Abundance tables (for the co-occurrence layer)

Because abundance co-occurrence is now a **core** Retes layer ([`03`](03_layer_factory_and_catalog.md), [`08`](08_decisions.md) C1), Mind must also ingest **per-sample abundance profiles** — from `curatedMetagenomicData` and GMrepo (human-gut-relevant), with MicrobeAtlas for breadth. These are staged like any other source (raw → reviewed), and feed a network-inference pipeline step rather than becoming findings directly.

## Mapping onto the existing schema

The current Django model already expresses the right shape (see `innovhealth_microbiome/database/models.py`, `docs/schema.md`):

```
Study ─▶ Group ─▶ Comparison ─▶ QualitativeFinding(taxon, direction)
                             └▶ QuantitativeFinding(taxon, value)
Taxon ─ TaxonClosure (lineage) ─ TaxonName (synonyms)
```

Disbiome maps cleanly: an Experiment → a `Comparison` (patient `Group` vs control `Group`) inside a `Study`, with its outcome → a `QualitativeFinding` (`direction ∈ enriched/depleted/…`) on a resolved `Taxon`. `TaxonClosure` already supports lineage-aware rollup, which the layer work depends on.

One correction inherited from the network review (see [`02`](02_retes_multiplex_model.md)): **one organism is one node**. The current graph code duplicates a taxon into separate "enriched" and "depleted" nodes; direction is a property of *evidence*, not of organism identity. Mind's canonical `Taxon` is already single-identity; the fix lives in Retes, not the schema.

## Making ingestion easier (principles only)

The current workflow — a curator hand-fills a multi-sheet Excel workbook matching strict contracts, gated on `paper.status = complete`, imported synchronously inside a web request — is the main usability pain point and is explicitly *not* the model going forward. The principles Mind should keep, independent of how Flux later implements them:

1. **Sources are adapters, not spreadsheets.** A Disbiome (or GMrepo, …) adapter pulls records via API/export; humans review, they don't transcribe.
2. **Provenance and review-state are first-class.** Every record carries where it came from and how trusted it is, through explicit states:
   `raw source record → candidate evidence → reviewed evidence`.
   Imported-but-unreviewed data is visible but never silently promoted to trusted curated evidence.
3. **Taxon resolution stays strict.** Names that don't resolve confidently to a canonical `Taxon` are flagged for review, not silently coerced — matching the existing preview-first behaviour.

Flux (the async engine that actually fetches, stages, resolves, and queues) and Curia (the review UI) are named here for completeness but designed later, from scratch. This doc commits only to: **Disbiome-primary, multi-source, provenance-first, API-driven, human-review-gated.**
