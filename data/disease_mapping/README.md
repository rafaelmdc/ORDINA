# Disbiome → MONDO disease crosswalk (interim)

This folder holds the disease-vocabulary mapping for decision [`D1`](../../docs/08_decisions.md) — standardising Disbiome's diseases onto **MONDO**. It is **interim**: a deterministic code-based pass (via UMLS) is pending and will raise coverage (see "Follow-up").

## Files
- **`disbiome_mondo_mapping.tsv`** — the mapping table (one row per distinct Disbiome disease).
- **`build_mondo_mapping.py`** — the reproducible script that generates it (pure stdlib).

## How it was built
Disbiome codes every disease with **MedDRA** (e.g. Crohn's = `10011401`). The clean way to reach MONDO would be a deterministic `MedDRA → MONDO` code join, but **MedDRA is licensed**, so MONDO's free release publishes only ~1,478 MedDRA cross-references (and EBI's OxO bridge is currently offline). So this interim pass maps by **MONDO label / synonym match**, with the MedDRA code used only as corroboration:

1. exact match of the Disbiome name to a MONDO **label** or **exact synonym** (after normalising case, punctuation, possessives, and British→American spelling);
2. MONDO **related synonym**;
3. the sparse **MedDRA xref** where MONDO happens to carry the code;
4. **token-subset** ("Hepatitis C" ⊆ "hepatitis C virus infection" — safe, since it can't match "hepatitis D");
5. typo-level **fuzzy** as a last-resort suggestion.

Tiers 1–3 (and unambiguous 4) are treated as **confirmed**; tiers 4-token/5 are **suggestions to confirm**.

## What's in the table (the `status` column is the important one)
| status | count | meaning |
|---|---|---|
| **confirmed** | 222 | exact label/synonym match, unambiguous — trust these |
| **review** | 84 | a *suggested* MONDO term that a human/agent must confirm (rollups, typos, broader/narrower) |
| **unmapped** | 49 | no MONDO candidate — needs curation (10 have no MedDRA code; the rest are compound/rare, e.g. "T2D with hyperlipidemia") |

- The **222 confirmed cover 76.9% of all Disbiome experiments** — every high-volume disease (Crohn's, colorectal cancer, Parkinson's, T2D, UC, IBS…) is confirmed and correct.
- **219** mapped rows also carry a **MeSH id** (the `mesh_ids` column) — the bridge vocabulary (GMrepo is MeSH-coded; literature validation works in MeSH).
- Cross-check: in the **37** rows where MONDO independently carries the MedDRA code, the name-match and the code **agree 37/37** (zero contradictions).

**Columns:** `disbiome_disease, meddra_id, mondo_id, mondo_label, mesh_ids, match_method, confidence, status, meddra_corroborates, ambiguous, n_experiments`.

## How to use it (for the build)
- Iteration 1 is **Disbiome-only**, so diseases can be keyed by their native **MedDRA** code; MONDO is a *normalization layer* added when a second disease source arrives (see docs [`01`](../../docs/01_mind_data_foundation.md), [`10`](../../docs/10_architecture_and_roadmap.md)). Populate `association.disease_mondo` from the **confirmed** rows now; leave it null for review/unmapped until curated.
- Do **not** auto-load `review`/`unmapped` rows as truth.

## Follow-up: the deterministic pass (raises coverage toward ~100% of coded diseases)
Once a free [UMLS API key](https://uts.nlm.nih.gov/uts/signup-login) is available, do `MedDRA → UMLS CUI → MONDO` (UMLS is the hub MedDRA and MONDO's source ontologies both map into). That resolves most of the `review`/`unmapped` tail deterministically, leaving only the genuinely uncoded/compound entries for hand curation.

## Regenerate
```
# needs: mondo.obo (http://purl.obolibrary.org/obo/mondo.obo) and the Disbiome sqlite
MONDO_OBO=/path/to/mondo.obo DISBIOME_DB=/path/to/disbiome.sqlite python build_mondo_mapping.py
```
MONDO release used: **2026-06-02**.
