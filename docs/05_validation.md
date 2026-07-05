# 05 — Validation: telling signal from artifact

> Discovery ([`04`](04_analysis_and_discovery.md)) is easy to fake — any rich network produces clusters and rankings. This doc is the discipline that keeps ORDINA scientific: for each kind of finding, how we test it, and — critically — **what each test can and cannot establish.**

## The core threats

1. **Phylogenetic confounding.** Related organisms trivially share metabolism, traits, and disease patterns. Structure that merely recovers the tree is not a discovery.
2. **Literature / curation bias.** Well-studied organisms and diseases have more edges everywhere. "Novel" predictions may just track study effort.
3. **Circularity.** Using the disease signal to predict disease associations recovers the input.
4. **Sparsity artifacts.** Missing genomes/annotations create absent edges that look like biological dissimilarity.

Every validation below targets one or more of these.

## 1. Phylogeny null (the mandatory baseline)

**Test:** compare every module, congruent edge, and prediction against what the **GTDB phylogeny layer** alone would produce, and against **degree-preserving randomization** (configuration-model rewiring that keeps each node's degree per layer) [[6]](refs.md).

**Establishes:** that a finding carries information *beyond* relatedness and *beyond* hub-ness.
**Cannot establish:** biological truth — only that the signal isn't a trivial artifact. This is a necessary, not sufficient, gate. Nothing proceeds to reporting without passing it.

## 2. Temporal held-out validation

**Test:** freeze an **older Disbiome snapshot**, build the multiplex, generate predictions, and test whether they are recovered by associations added in **later** snapshots. This mirrors the MultiXrank supervised design (train on outdated associations, evaluate on novel ones) [[7]](refs.md).

**Establishes:** genuine predictive power for *future-discovered* associations — the strongest purely-computational evidence available.
**Cannot establish:** associations that are real but still undiscovered by anyone (they look like false positives). So precision is a lower bound, not the truth.

## 3. Cross-source concordance

**Test:** for each association or layer edge, check agreement across *independent* curated sources — Disbiome vs **GMrepo** [[8]](refs.md) vs **gutMDisorder** [[9]](refs.md) — and for enrichment edges, whether an independent database supports the same relation.

**Establishes:** robustness against any single source's idiosyncrasies and curation errors.
**Cannot establish:** correctness where *all* sources share the same upstream bias (e.g. the same over-studied taxa).

## 4. Literature co-occurrence check (with a bias warning)

**Test:** for a predicted disease–organism pair, query **Europe PMC** / **PubTator 3.0** [[21]](refs.md) for co-mention and relation annotations. A prediction that is *newly* co-mentioned after the training cutoff is corroboration.

**Establishes:** weak, cheap corroboration and useful triage.
**Cannot establish:** much on its own — co-mention is not association, and using literature co-occurrence both as evidence *and* (via MINERVA-style resources) as a comparator risks **circularity and literature bias**. Explicitly treated as a soft signal, never a ground truth.

## 5. Negative controls and sanity checks

- **Label permutation:** shuffle disease labels; the discovery pipeline should lose its signal. If it doesn't, the pipeline is finding structure in noise.
- **Coverage stratification:** confirm predictions aren't purely explained by node coverage/degree (well-annotated organisms winning by default). Report performance within coverage strata.
- **Layer ablation:** re-run discovery dropping each layer; a finding that survives ablation of any single layer is more robust than one propped up by one layer.

## 6. Prospective / experimental framing

The honest ceiling of computational validation is "consistent with, and predictive within, existing knowledge." Genuine confirmation is prospective:

- **New-cohort test:** does a predicted association hold in a microbiome dataset not used anywhere in construction?
- **Wet-lab framing:** for a top mechanistic hypothesis (e.g. predicted cross-feeding underlying a co-occurrence), what is the minimal experiment — co-culture, metabolomics, gnotobiotic model — that would confirm or refute it?

ORDINA's deliverable to a researcher is a **ranked, mechanism-annotated, uncertainty-quantified shortlist** with an explicit "how you would test #1" — not a claim of established fact.

## 7. Reporting standard

Every reported finding carries: the supporting layers, its phylogeny-null result, its temporal-holdout and cross-source status where applicable, and a provenance trail to source evidence. Findings that pass only the null gate are labelled *exploratory*; findings that also survive temporal holdout and cross-source concordance are labelled *supported*. Nothing is labelled *confirmed* without external (prospective/experimental) evidence.
