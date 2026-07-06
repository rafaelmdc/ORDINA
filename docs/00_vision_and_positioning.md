# 00 — Vision and Positioning

## The problem that forced a pivot

ORDINA began as a manually-curated microbiome↔disease database. That premise collapsed on discovering **Disbiome** [[1]](refs.md), which already does exactly that, and does it well: a standardized, MedDRA-coded, NCBI/SILVA-linked curated database of published microbiota–disease associations (~190 diseases, ~800 organisms, ~500 papers at publication), with study-quality scoring and a JSON API. Curating more associations by hand would be a strictly worse Disbiome. Manual curation also does not scale — the same conclusion reached by the MiDRED corpus authors, who built annotated data precisely because expert curation cannot keep pace with publication volume [[2]](refs.md).

**So the database cannot be the contribution.** The contribution has to be what we *do* with association evidence once we stop treating it as the end product.

## What ORDINA is

> ORDINA is an **organism-resolved disease interaction network atlas**: it converts microbiome association evidence from curated databases into a **multiplex network of organisms**, enriched across many independent biological modalities via [Braidworks](https://github.com/rafaelmdc/braidworks), and analysed to surface organism modules, cross-layer structure, and candidate associations that a flat association list cannot reveal.

Three commitments distinguish it:

1. **Provenance-first.** Every edge and annotation traces to a source record. Imported, candidate, and reviewed evidence never mix silently.
2. **Organism-resolved and multiplex.** One organism is one node. Its relationships to other organisms are decomposed into *layers* — metabolic, ecological, phylogenetic, chemical — each an independent, reproducible view. Analysis happens *across* layers, not on one merged graph.
3. **Reproducibly enriched.** Enrichment is not hand-annotation and not LLM extraction from prose. It is deterministic database federation through Braidworks (the project's data-access library), so every layer can be rebuilt and audited.

## Competitive landscape

The microbiome-knowledge space already has several resources. ORDINA must be honestly distinct from each, not a re-skin.

| Resource | What it is | What it gives | What it is *not* |
|---|---|---|---|
| **Disbiome** [[1]](refs.md) | Manually-curated microbe–disease association DB | Standardized, quality-scored associations with taxonomy + MedDRA coding | Not a network; no cross-modality enrichment; no analysis layer |
| **MINERVA** [[3]](refs.md) (2025) | LLM + NER extraction of microbe–disease triples from ~130k papers; a single ontology-driven knowledge graph (66k relations) with link-prediction and a chat interface | Scale and sentence-level evidence; flat KG link prediction | **Not a multiplex** — one merged graph, one relation family (microbe–disease); enrichment is literature co-mention, which inherits literature bias |
| **MMiKG / MGMLink** [[4]](refs.md) | Path-mining knowledge graphs for microbiota–disease mechanistic hypotheses | Mechanistic paths across heterogeneous nodes | Heterogeneous KGs, not organism-resolved multiplex layers; not reproducible database-federation enrichment |
| **ORDINA** | Organism-centric **multiplex** built on curated seeds + Braidworks enrichment | Cross-layer organism structure, module discovery, layer-informed novelty, provenance | Not a bigger curated DB; not a flat literature KG |

### The sharp difference from MINERVA

MINERVA is the closest neighbour and worth stating precisely. MINERVA scales *one* signal — microbe–disease co-mention in the literature — into a large flat graph, then does link prediction on it. Its edges are only as trustworthy as literature co-occurrence, and its structure is single-relation. ORDINA instead keeps the disease signal deliberately *small and curated* (Disbiome-grade), and puts its effort into **many orthogonal, mechanistic enrichment layers** among organisms. The disease layer is the thing we want to *explain and extend*, not the thing we scale. That makes ORDINA's central object a genuine multiplex (same nodes, many independent edge types) rather than a large single-relation KG. The honest distinction is the **clean shared node set**: heterogeneous KGs can and do run random walks and community detection (MultiXrank itself is multilayer-general), but multiplex-*modularity* and cross-layer *congruence* — "is this organism module coherent across independent modalities?" — are well-posed only when every layer shares one node set, which a flat microbe–disease KG does not have [[5]](refs.md)[[6]](refs.md)[[7]](refs.md).

## The falsifiable value proposition

ORDINA earns its existence only if the multiplex structure produces something the underlying association list does not. Concretely, ORDINA claims:

1. **Structure:** organisms cluster into modules that are coherent *across independent layers* (e.g. a group that is both metabolically complementary and co-perturbed in a disease), and these modules are not explained by phylogeny alone.
2. **Novelty:** organisms strongly connected in enrichment layers (metabolic/ecological/chemical) but *absent* from the disease layer are enriched for genuine, later-confirmed disease associations — testable by temporal held-out and independent-source checks (see [`05_validation.md`](05_validation.md)).
3. **Explanation:** for a known disease–organism association, the layers provide a candidate *mechanistic context* (shared pathway, niche, metabolite exchange) rather than a bare edge.

If none of these beat the baselines — a **phylogeny null** (related organisms trivially behave alike), a **study-effort null** (well-studied organisms show up everywhere — the bias the coverage audit confirmed), and a flat-graph baseline — the multiplex is decoration and we should say so. That test is the recovery metric ([`09_recovery_metric.md`](09_recovery_metric.md)) and it is built into the plan from the start.

## Scope of this repository

Docs-only, this round. It fixes the scientific framing — vision, network model, layer set, analysis and validation strategy — so that implementation (Mind migration, Retes construction, Flux/Curia from the ground up) can begin against a rigorous, agreed blueprint rather than being reverse-justified later.
