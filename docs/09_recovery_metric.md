# 09 — The recovery metric (the "does it actually work?" test)

> **What this doc is.** Decision [`08`](08_decisions.md) A2 says the planning phase ends and building begins once we have a **recovery metric** that is *defined, measurable, and beats the baselines on hidden data*. Doc [`05`](05_validation.md) §0 names that metric; **this doc makes it concrete** — exactly what we predict, what we hide, how we score it, what we compare against, and what number means "pass." Written plainly so it can be built from directly.
>
> **The one-line idea:** hide some disease–organism links we already know are real, try to predict them back using only the *biology* layers, and check that we do meaningfully better than two dumb shortcuts — "related bugs behave alike" and "famous bugs win." If we can't beat those shortcuts, the network has added nothing and we do not proceed.

---

## 1. The task, in one sentence

**Given a disease, rank all organisms by how likely they are to be associated with it — using only the biology layers — and check whether the organisms we secretly *know* are associated (but hid) land near the top.**

This is a ranking test. We are not asking for a yes/no on every organism; we are asking whether the true, hidden partners of a disease float to the top of a ranked list.

## 2. How one prediction is made

We use **random walk with restart** on the multiplex (the method MultiXrank is built for [[7]](refs.md)). Plainly:

- Picture the organism network with its **biology (enrichment) layers** stacked up — shared metabolism, shared traits, phylogeny, co-occurrence. **The disease co-signature layer is deliberately *not* in this stack** (see the box below).
- **The seed = the disease's *kept* partner organisms** — the ones still visible after hiding (§3). Drop a marble on them and let it wander the biology layers, occasionally teleporting back to the seed so it stays local.
- Wherever the marble spends the most time = the organisms most connected, *through biology*, to that disease's known members.
- Rank organisms by marble-time. That ranked list is our prediction for that disease; the true **hidden** partners should be near the top.

The seed is injected through the **bipartite disease→organism coupling** (doc [`02`](02_retes_multiplex_model.md) §4) using only the *kept* edges, so seeding a disease and walking the biology layers is one well-defined operation.

> **Why the disease co-signature layer is excluded from the predictor.** That layer links organisms *because they share diseases* — it is built from the same signal we are trying to predict. Walking it to predict disease links would be "disease predicting disease," which muddies the A1 claim ("does *biology* explain disease?") and risks leaking the target. So the headline metric walks **enrichment layers only**. A useful side effect: the enrichment layers are **disease-independent**, so they do **not** need rebuilding for each split — only the seed (kept links) and the target (hidden links) change per fold. (A separate, clearly-labelled *disease-informed* variant — and the cross-disease / guilt-by-association findings of [`08`](08_decisions.md) A4 — *may* use disease signal as a predictor, but then must obey guard (a) below. Those are secondary findings, not the A1 gate.)

## 3. What we hide — the careful part (this is where cheating hides)

To test prediction honestly we hide some known links, predict, and check recovery. Three things must be right or the test secretly cheats (see [`08`](08_decisions.md) A4, "don't grade your own homework"):

**a) Any disease-derived layer used as a predictor must be rebuilt *without* the hidden links.**
For the **headline biology-only metric this is automatic** — the disease co-signature layer is excluded from the predictor entirely (§2 box), so there is nothing to leak. The guard bites only for the *secondary* disease-informed variants (and the A4 cross-disease / guilt-by-association findings): if any layer derived from disease associations is walked, it must be **rebuilt from scratch using only the kept links** each time, or the hidden answer is still sitting in the network and the test is meaningless.

**b) Keep look-alike diseases together when splitting.**
Crohn's disease and ulcerative colitis share most of their biology. If we hide a Crohn's link but leave the near-identical UC links in, we've basically left the answer in plain sight. So before splitting, we **group diseases that are highly similar** and split by *group*, never by individual link. All of a disease-group's links go to the same side (kept or hidden) together.

*How the grouping is computed matters, or it leaks too.* Prefer a **link-independent** similarity — the **MONDO hierarchy** ([`08`](08_decisions.md) D1) or disease-name similarity — because it is defined outside the exact organism links being scored, so a global grouping is safe. The **shared-organism-overlap fallback** (used while MONDO is deferred, [`10`](10_architecture_and_roadmap.md)) *is* defined on the links, so it must be computed **per fold, from the kept/training links only** — never from the union of kept+hidden, or the fold boundaries have peeked at the test set. Same discipline applies to the study-effort and enrichment-coverage baselines (§5) and to any supervised per-layer weighting ([`08`](08_decisions.md) B2): all fit on training links only, recomputed per fold.

**c) Decide who is even eligible to be predicted.**
An organism with **no biology data at all** (a "dark" node, ~13% of taxa — [`08`](08_decisions.md) B5) cannot be reached by the marble through biology layers, because it has no biology edges. It could only be "predicted" from the disease signal itself — which is excluded from the headline predictor (§2 box). So dark nodes are **not part of the pass/fail number**; we report them separately (§7). The headline metric is measured over organisms that actually have biology to walk on.

### The two splits we run

- **Primary — grouped cross-validation.** Split the disease-groups into 5 equal parts. Five times over: hide one part, take the other four as the kept/seed links, predict, score. Average the five scores. (The enrichment layers themselves don't rebuild per fold — they're disease-independent, §2 box — only the seed/truth sets change.) ("Cross-validation" = rotate which slice is hidden so every link gets tested exactly once.)
- **Stronger — temporal split.** Freeze an **older Disbiome snapshot**, predict, and check recovery against links that appeared in **later** snapshots (doc [`05`](05_validation.md) §2). This is harder and more honest — it mimics predicting the actual future — so it is the stronger evidence when it agrees with the primary split.
  - **Feasibility caveat:** this assumes we can actually reconstruct an older Disbiome snapshot (a dated export, or an archived copy). Disbiome refreshes on a manual cadence and may not expose retrievable historical versions. If it doesn't, we either **start archiving our own dated pulls from now on** (so the split becomes available later) or fall back to the grouped cross-validation split alone. The pass/fail bar must not *depend* on the temporal split being available — it is corroboration, not the primary gate.

## 4. The score

For each disease we produce a ranked list of organisms; the true hidden partners should sit near the top. We measure that with:

- **Recall@k (primary, plain to read).** Of the hidden true partners of a disease, what fraction land in the **top *k*** of the ranked list? (e.g. *k* = 20). "We recovered 14 of 20 hidden Crohn's organisms in the top 20" is a Recall@k of 0.7. Intuitive, and it's exactly the question a user cares about — *are the right answers near the top?*
  - *Fairness caveat:* if a disease has **more than *k*** hidden partners, Recall@k is capped below 1 and unfairly penalises well-studied diseases. So we (i) **fix *k* in advance** at roughly the median partner count, and (ii) also report **R-precision** — precision at *k = the number of that disease's hidden partners* — which self-adjusts per disease and removes the cap.
- **Hits@k.** Did *at least one* true partner make the top *k*? A coarser, per-disease yes/no, useful when a disease has few known partners.
- **AUPRC (secondary).** "Area under the precision–recall curve" — a single number summarising the whole ranked list, not just the top *k*. We use the precision–recall version (not the more common AUROC) **because true links are rare**: with thousands of organisms and only a handful truly linked to a disease, a metric that rewards ranking the rare positives high is the honest one; AUROC looks flatteringly high even for weak predictors when negatives dominate.

**Which diseases we score.** Recall/precision are unstable for a disease with only one or two hidden partners, so we evaluate over diseases with at least a small minimum of known partners (e.g. ≥ 5; the exact floor fixed in advance and reported). We compute each metric **per disease, then average across diseases** (so a few heavily-studied diseases don't dominate), and report the spread, not just the average.

## 5. The baselines we must beat — the entire point

A good-looking recovery number is worthless on its own, because a few stupid shortcuts already recover a lot. We must beat **all** of these, run through the *identical* hide-and-predict procedure:

- **1. The "related bugs behave alike" baseline (phylogeny null).** Predict using **only the GTDB phylogeny layer** [[14]](refs.md) — rank organisms purely by how closely related they are to the disease's known members. Related organisms trivially share diseases, so this baseline is already decent. **If the full multiplex can't beat it, all our biology layers added nothing beyond the family tree** — the single most important comparison (doc [`05`](05_validation.md) §1).
- **2. The "famous bugs win" baseline (study-effort null).** Rank organisms by **how well-studied they are** — how many Disbiome experiments / how many links they have — ignoring the specific disease. This directly operationalises the **coverage-bias finding from the audit**: well-studied organisms show up everywhere, so a predictor can score well just by always guessing the famous ones. **If we can't beat this, we're rediscovering fame, not biology.** *(Studiedness must be counted from the **kept/training links only**, never the held-out ones — otherwise the baseline itself peeks at the answer.)*
- **3. The "shuffled network" baseline (degree-preserving random null).** Randomly rewire the network while keeping each organism's number of connections the same (configuration-model rewiring), then predict. This checks we're not just exploiting hub organisms.
- **4. The "just has biology" baseline (enrichment-coverage null).** Rank organisms by **how much biology they carry** — number of enrichment layers present + their degree across those layers — computed from **training data only**. This is the twin of baseline 2 that closes a gap it misses: enrichment *coverage* is itself study-effort-biased (the D2 audit), so a predictor can beat "famous by disease-link-count" while still just winning on "has a genome / has traits." If the multiplex can't beat this, it is exploiting *data availability*, not disease-specific biology.

Beating baselines **1, 2 and 4 is the real bar** (relatedness, disease-fame, and data-availability-fame). Beating 3 is a basic sanity floor.

**One extra control for the phylogeny comparison (the rollup entanglement).** Genus-primary analysis lets a genus "light up if any child species has data" and lets signal propagate up the taxonomy ([`08`](08_decisions.md) B5) — so an enrichment layer's genus signal and the phylogeny null can share a common cause (relatedness), which would make "beats phylogeny" easier than it looks. To keep that honest we add a **propagation-only control**: build each enrichment layer's genus signal by *pure species→genus propagation with the biology stripped out*, and require the real layers to beat **that** too. "Beats the phylogeny null" is defined operationally as the paired-bootstrap CI of *(multiplex − phylogeny)* staying above zero (§6, raw scores, not residualized), now backed by this propagation-only check so the win can't be pure rollup-by-relatedness.

## 6. How we decide we actually "beat" them

We don't just check that our average is bigger — a bigger average can be luck. We use a **paired bootstrap**: re-draw the set of diseases with replacement many times, and each time score **both our model and the baseline on the *same* resampled diseases**, recomputing *(our score − baseline score)*. Pairing matters — our model and the baseline are evaluated on identical held-out data, so the paired difference is what carries the signal. We claim victory only when that difference's confidence interval **stays above zero**, and we report **how much better** (the effect size), not just "it's significant" — a win that's statistically real but tiny is not a reason to build.

**Guarding against fishing.** We compare against several baselines, on several metrics, at a chosen *k* — many comparisons, so some will look good by chance. To avoid cherry-picking, the **primary test is fixed in advance** — one metric (Recall@k at the pre-set *k*), one rank (genus), against the **three baselines that matter (phylogeny, study-effort, and enrichment-coverage)**. Everything else (AUPRC, R-precision, per-stratum breakdowns, the degree null, the propagation-only control) is **secondary/supporting**, reported but not the thing the gate turns on.

We also run the **label-permutation sanity check** (doc [`05`](05_validation.md) §5): shuffle the disease labels and confirm the whole thing collapses to baseline. If it doesn't, our pipeline is finding "signal" in noise and everything above is void.

## 7. Coverage honesty (report, don't hide)

Because coverage is uneven and biased (the audit), we always report recovery **broken down by how much biology a node has**, not just one blended number:

- recovery over **well-covered** organisms (many layers present),
- recovery over **thinly-covered** organisms,
- and **dark** organisms noted as *not evaluable by biology* — they can only ever be gap-flags and hypothesis targets (B5, and the "guilt-by-association as an output, not a feature" point in A4), never part of the pass/fail score.

This stops us from quietly reporting a good number that only holds for the famous, data-rich organisms.

## 8. Which rank we score at

Primary scoring is at **genus** (decision B1 — genus is the most robust, best-covered level). Disbiome links given at species (or finer) are rolled up to genus for the headline number; **species-level recovery is a secondary drill-down** where the data supports it. Rolling up also softens the coverage gaps (a genus counts as having biology if any of its species does — B5), but any recovery that leans on that rollup still has to clear the phylogeny baseline, because "related things look alike" is exactly what rollup-by-relatedness produces.

## 9. The "explain" half (secondary output, not pass/fail)

A1 asks us to *recover **and explain*** known links. Recovery is the number above; explanation is an **annotation on each recovered link**: which layers carried the marble to it (found by re-running the walk with each layer removed and seeing which removal hurts — "layer ablation," doc [`05`](05_validation.md) §5). This produces, per recovered association, a short "explained by: shared metabolism + shared niche" tag. It is a **reporting output**, not part of the pass/fail metric — but it's what makes a recovered link *useful* rather than just *counted*.

## 10. The pass bar (the concrete exit criterion)

**We stop planning and start building when, on the hidden-data test:**

1. the pre-registered primary test passes — the full multiplex's **average genus-level Recall@k (at the fixed *k*) over covered organisms** is **reliably higher than the phylogeny, study-effort, and enrichment-coverage baselines** (§5 items 1, 2 & 4), by a margin the paired bootstrap keeps above zero (§6);
2. **if a reconstructable older Disbiome snapshot exists**, the temporal split **agrees in direction** with the primary split (it may be weaker, but it must not contradict); **if none is available at gate time**, the gate rests on the grouped-CV primary test + permutation + the coverage-stratum condition below, and temporal validation becomes a post-gate commitment (we begin archiving dated Disbiome pulls immediately, [`10`](10_architecture_and_roadmap.md) Slice 0, so it matures for iteration 2). The bar must never *depend* on the temporal split being available (§3);
3. the **label-permutation check collapses** to baseline (§6);
4. and recovery is **not confined to the well-covered stratum** — it survives, even if reduced, on thinly-covered organisms (§7).

**On the absolute number:** we deliberately do **not** fix a magic threshold (e.g. "Recall@20 > 0.5") up front, because a fair target can only be set once we see how high the phylogeny baseline itself reaches — the honest bar is *"beats the phylogeny, study-effort and enrichment-coverage baselines by a real margin,"* with the effect size reported, not a number picked blind. The first run's baseline scores set the reference for every run after.

## 11. What this test does *not* prove (so we don't oversell it)

- **Recovering known links is not discovering true ones.** It shows the machine reconstructs what's already known; novel prediction is a separate, later claim (A1, iteration 2).
- **Precision is a floor, not the truth.** A "wrong" top-ranked prediction may be a real association nobody has found yet — so our measured precision *understates* real precision (doc [`05`](05_validation.md) §2).
- **Beating the nulls is necessary, not sufficient.** It proves the signal isn't a trivial artifact of relatedness, fame, or hubs — nothing more. Biological truth needs the external and prospective checks in doc [`05`](05_validation.md) §§3–6.
