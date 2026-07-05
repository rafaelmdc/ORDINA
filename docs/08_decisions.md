# 08 — Resolved decisions

> This doc records decisions taken on the open questions in [`06_open_questions.md`](06_open_questions.md), from a mix of reasoning and the user's domain/priority calls. Where an item here conflicts with an earlier doc, **this doc wins** and the earlier doc has been updated to match. Items still genuinely open are listed at the end.

## A. Scientific framing

- **A1 — First goal: recover-and-explain-known (validation-first).** *(user call)* The first iteration's headline claim is: the multiplex **re-derives known disease–organism associations** and annotates each with the **layers that explain it** (shared metabolism, niche, observed co-occurrence…). Rationale: this is the credibility gate — novel predictions are only trustworthy once recovery provably beats the null. Discovery (the layer-discordance heuristic) is explicitly the *second* iteration.
- **A2 — "Decent enough" exit criterion.** *(resolves Q12)* The docs phase ends and building begins when: (a) a **recovery metric** — known-association recovery beating the phylogeny null on a held-out split — is defined and measurable; (b) the layer set, operating rank, and disease vocabulary are fixed (this doc); and (c) the coverage audit (D2) confirms enough enriched nodes to be worth it. The milestone is tied to A1, not to feature count.
- **A3 — Operational "novel."** *(resolves Q5)* A candidate is *novel* if it is **absent from every curated seed source at snapshot time** and is surfaced purely from enrichment layers **with the disease layer held out**. Deferred to iteration 2 per A1, but defined now so the firewall is unambiguous.

## B. Modelling

- **B1 — Operating rank: dual-rank.** *(user call, Q3)* Nodes are maintained at **both genus and species**. **Primary analysis runs at genus** (most robust, best coverage — 16S disease data is genus-reliable); **drill-down to species** where the data supports it. Consequences, now mandatory:
  - Every **layer factory must declare its native rank and an explicit aggregation rule to genus** (e.g. metabolic reconstructions are genome/strain-level and must define how strain→species→genus aggregation works).
  - Rollup uses `TaxonClosure`, and must **preserve and surface species-level contradictions** rather than averaging them away (a genus can look "neutral" while its species disagree — that disagreement is a finding, not noise).
  - Default reporting is at genus; species detail is a drill-down, not a separate network.
- **B2 — Cross-layer weight normalization.** *(resolves Q2)* Normalize each layer's weights **within the layer** (rank/quantile → [0,1]); retain raw weights as provenance. Inter-layer coupling strength for supra-adjacency is **tuned by sensitivity analysis**, not assumed.
- **B3 — Measured-absent vs unmeasured.** *(resolves Q4)* Three-state edge presence (present / measured-absent / unmeasured) via the layer coverage flag. Analyses run on the **measured-induced subgraph** per layer; unmeasured is never silently treated as zero-similarity.
- **B4 — Multiplex vs heterogeneous pivot trigger.** *(resolves Q1)* Stay organism-centric multiplex. Pivot to heterogeneous multilayer **only** when we concretely need to *rank non-organism endpoints* (pathways, metabolites, drugs) — an explicit decision, never drift.

## C. Layers

- **C1 — Abundance co-occurrence promoted to a CORE layer.** *(user call, Q9)* No longer "future." Rationale and specifics:
  - **The synergy that justifies early inclusion:** the **metabolic layer *predicts* interaction** (complementarity/exchange from reconstructions), while the **co-occurrence layer *observes* it** (organisms that actually co-vary across samples). **Congruence between predicted and observed interaction is a headline cross-layer analysis and a strong internal validation** — neither layer alone gives it.
  - **Sources:** prioritize **human-gut-relevant abundance** — `curatedMetagenomicData` and GMrepo abundance profiles — over environmental **Earth Microbiome Project** (EMP is breadth, not disease-relevant); **MicrobeAtlas** for scale.
  - **Inference method matters (correctness):** microbiome abundances are **compositional**, so naive Pearson/Spearman correlation is **forbidden** (spurious negative correlations). Use compositionally-aware inference — **SPIEC-EASI**, **SparCC**, or **FlashWeave**.
  - **Cost accepted:** this adds abundance-table ingestion to Mind and a network-inference step to the pipeline (Nextflow). Worth it for the observed-ecology signal and the metabolic-congruence check.
- **C2 — Updated core enrichment set** (see [`03`](03_layer_factory_and_catalog.md)):
  1. **Metabolic** (KEGG/MetaCyc/AGORA) — predicted interaction, top priority.
  2. **Abundance co-occurrence** (SPIEC-EASI/SparCC on curatedMetagenomicData/GMrepo) — observed ecology. **New core.**
  3. **Phylogeny / GTDB** — the control/null layer.
  4. **Ecophysiology** (BacDive + ProTraits + Madin) — niche overlap.
  5. **BGCs** (antiSMASH/gutSMASH) — exploratory, second wave.
  Plus the **disease co-signature** target layer (from Mind).

## D. Data and interoperability

- **D1 — Disease vocabulary: MONDO.** *(user call, Q10)* Standardize all sources onto **MONDO**. Map Disbiome's MedDRA → MONDO and GMrepo/gutMDisorder vocabularies → MONDO; **keep source-native codes as provenance**. This is what makes cross-source concordance ([`05`](05_validation.md)) meaningful, and MONDO's cross-references (MedDRA/DO/EFO/OMIM) make the mapping tractable.
- **D2 — Coverage audit is the first empirical task.** *(resolves Q8 as an action, not a decision)* Before trusting any layer: for each layer, measure **what fraction of Disbiome taxa (at genus and species) actually get enriched** — have genomes/reconstructions/traits/BGCs/abundance profiles — and **whether that coverage is biased** toward well-studied organisms. A layer that only covers the already-famous taxa is close to useless and we need to know that up front.

## E. Process / still open

- **E1 — Flux and Curia** are designed ground-up later *(Q11 — deferred, unchanged)*.
- **E2 — Iteration cadence.** With A1–D2 fixed, the remaining pre-build work is the **coverage audit (D2)** and the **MedDRA/GMrepo → MONDO mapping (D1)**; both are empirical and are the natural next hands-on steps once the docs are agreed.

---

### Change log triggered by these decisions
- [`03`](03_layer_factory_and_catalog.md): co-occurrence moved from "future" (§5) into the core enrichment set; native-rank/aggregation added to the factory contract.
- [`02`](02_retes_multiplex_model.md): operating rank changed to dual-rank.
- [`01`](01_mind_data_foundation.md): abundance-table ingestion + MONDO harmonization added.
- [`05`](05_validation.md): metabolic-vs-co-occurrence congruence added as a validation signal; recovery-first metric noted.
- [`07`](07_stack.md): co-occurrence network-inference step + `curatedMetagenomicData` added to the pipeline.
- [`06`](06_open_questions.md): resolved items annotated and pointed here.
