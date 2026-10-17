# Simulated reviewer report, round 3: docs/paper/main.pdf (8 pages body + 2 pages references) and supplement.pdf (9 pages)

Stance: critical but fair, ICRA/IROS/RA-L. Sources read: `main.tex`, `supplement.tex`, `numbers.tex`, `tab_h_*.tex`, `tab_r.tex`,
`tab_i13_dev.tex`, `experiments/PREREGISTRATION_H.md`, `experiments/results/h_summary.json`, `h_change_rate.json`.
I rendered `main.pdf` and `supplement.pdf` to PNG (`scratchpad/r3/`) and inspected Table I-IV, Fig. 5 (change-rate model) and
Supp. Fig. S5 (case study). I did **not** open the J ledger or any P2 output, so J and P2 are judged on design only
(13 red `TBD` remain in `main.pdf`: abstract, P2 paragraph, campaign J paragraph, conclusion).

Recommendation (detail in Sec. 4): **borderline**, confidence 3/5. Up from "borderline, leaning weak reject" in R2.
The paper now fits 8 pages, the hidden-fire story and the memory story are both evidenced, and the audit is unusually
transparent. It is still simulation-only, J and P2 are unfinished, and the new memory contribution is weaker than the
abstract makes it sound.

---

## 1. Status of the R2 weaknesses N1-N7

| # | Status | Evidence (current files) | What is still open |
|---|---|---|---|
| N1a Proposition 1 trivial / overclaimed | **Partly** | Demoted to "Observation 1" and "Corollary 1" (main.tex l.230-245); "elementary by design" stated (l.234); two caveats added (l.247-250); the run audit rejects any memory threshold above $\tau_h$ (l.275). | Corollary 1 says $\Pr[\text{unsafe}]\le\varepsilon$ "for every visiting order". That is wrong by a factor up to 2: see 2.4. The exposure term I asked for in R2 is only half-present ("transfers only to the extent that $\varepsilon$ is uniform", l.247-248). The cost side of the invariant (false stops from caution) is still unmeasured. |
| N1b H is a straw man | **Partly** | H is now run: M0 1/32, M1 20/32, M2 0/32 unsafe (`tab_h_arms.tex`). All 32 missions are in Supp. Table S8. Fig. 5 (change-rate model) is in the main text with a recency-gated M1age arm and says "model prediction, not an observation". Supp. says "no break-even point" for $q\in[0,0.5]$. M1's fast-and-wrong behaviour and its 4 false refusals are reported. | The p-value $1.9\times10^{-6}$ is still presented as evidence (Sec. V-E) with no "by design" label and treats the 32 missions as independent. M1age is a model curve, not an executed arm. P1 is still evaluated only on the 8 persistent-relocation missions. The reader of the main text never sees that M2 is slower than M0 in the 8 relocation-change missions (Supp. S8: e.g. Q02.3 85 s vs 114 s, Q15.2 125 vs 116 s). |
| N2 P: 64% false alarms vs "fail-closed and useful" | **Partly** | The abstract now carries 298/300 and 64/100 and says a site-specific threshold is needed (abstract l.46-47). Licence sentence fixed in Supp. (original LICENSE, mirror used). | P2 is `TBD` in the body. No ROC / AUROC. $\tau_h^{\mathrm{mem}}=0.01$ is never reconciled with P (see 2.3). R's clean set has zero errors, so it cannot show degradation-induced misses (see N7). |
| N3 scope creep, version zoo, length | **Partly** | Body is 8 pages. A "Terms" paragraph defines v3.4/v3.5/v3.6, visible/perceivable, campaign, expected behaviour (l.94-100). "Jev" no longer appears in the abstract. | Still 12 studies and 5 headline contributions. The 4-line title ("Verify, Look Again, Remember: ... Safety-Monotone Mission Memory ...") is hard to parse. The abstract is about 420 words. "Jev" is still a section name and is still not explained to readers (l.204-212). Arms A/B/C of different studies are gone, but "Jev-role model" appears in Algorithm 1. |
| N4 Two-model claim | **Partly** | Abstract now says "original two-model design ... Cloudflare's Clef-Flash, a post-trained Qwen model" and no longer says "differently trained". Text states shared lineage and "the correlated-failure caveat applies in full" (l.207-209). | No conditional-miss analysis, although the data exist: dev table (`tab_i13_dev.tex`) shows v3.6 alone misses 17 fires and Clef+Qwen "both approve" misses 15, so Clef also misses at least 15 of the 17 (at least 88%). Clef alone is still not discussed economically. J is still confounded (4B + Clef vs 9B v3.6, different prompts) and the registered claim is "no extra risk", which 0 vs 0 cannot support. J is `TBD`. |
| N5 headline numbers read stronger than they are | **Partly** | G: conditional denominator is defined in Terms and in the sentence; "+32 s" is one measured number (l.197-198), the "60 s" claim is now 39 s. | E (60/60) is still stated in the abstract without "v3.5 delivered despite a small fire in 12 of 13 worlds in F" (the number is in Sec. V-C but not next to the headline). Unconditional G rate (13/24 vs 23/24, macros `GCorrectB/C`) is defined but unused. Supp. l.157 still says of F's six misses "no threshold can separate them" without the fire-free distribution of the same worlds. "B0 = 40" remains in the abstract (it is a counterfactual by definition). |
| N6 pre-registration credibility | **Partly** | Table S7 lists commits and dates; the "Each was registered before its first trial" caption in Table I is still there; T1 amendment count shown. The 10 000 px cut is labelled "not registered" (Sec. V-A). The "any change on T2 (a power failure)" wording is now explicit. | Everything is 2026-10-16/17 and in the authors' own repo. No external timestamp, and the text never says the studies are *chained* (F after T1/T2, G after F, H after G, P2 after P): it should say "confirmatory within a study, sequential across studies". Study C is still excluded from the Table I claim. H had a mechanics pilot and Amendment 1 (a "remembered-supply fix") before the registered trials; the pilot is listed in the registration but not in the paper. |
| N7 smaller methodological issues | **Mostly open** | R (`tab_r.tex`) is now filled, with per-condition rows; Table Z is retained with a sentence on CLIP. | Z still compares against a CLIP that refuses everything, no non-contrastive baseline, no matched-recall comparison; "hazard probability" is still called a probability although P shows a 1-2 orders of magnitude shift between renders and photos; the within-arm dependence of H (M2's mission-3 memory depends on its own mission-2 perception; M1's mission-3 failures are often caused by its own mission-2 failure) is not stated; R's CI is degenerate (see 2.5). |

---

## 2. The memory contribution after campaign H

### 2.1 What is convincing
- The design is clean and falsifiable. Four stories with four sequences each, arm order rotated, mask-based labels fixed before trials (`PREREGISTRATION_H.md` l.36-69).
- The result is not subtle: naive memory 20/32 unsafe (12 wrong supply, 8 into fire), verified 0/32, memory-free 1/32; all 112 trials audited, no stack failures.
- The honest parts are all there: M1 is 3x faster (28 s vs 73 s) and wrong; M2 pays a detour when the world changes back; the single case where caution mattered (Supp. Fig. S5: M0 left view $p_h=0.035$, M2 $0.049$) is shown with the claim restricted to "not less safe".
- The change-rate figure (Fig. 5) is the right headline and is in the main text. It correctly shows that the safe policy only buys 14 s at $q=0$ and 9 s at $q=0.2$ (85.5 to 71.3 s; 80.4 to 71.7 s), converging to M0 at $q=0.5$. A reader sees the honest size of the benefit.

### 2.2 What a reviewer will still attack, with numbers

1. **Scripted stories decide the headline.** Counting from Supp. Table S8, M1's 20 unsafe missions are exactly: 8 in S1 (both missions), 4 in S2 (mission 3), 8 in S3 (both missions); S4 gives 0 unsafe and 4 false refusals. M1 is unsafe in every mission in which the world changed *and* in every mission that follows a mission in which M1 skipped a check (S1.3, S3.3 are "persist" transitions but M1 fails there because its own mission-2 memory was poisoned by its own unchecked delivery). So 20/32 is a function of (story mix) x (M1 never verifies), not an estimate of anything. The paper says so only for Fig. 5, not for the McNemar p-value.
2. **Non-independence.** The 32 missions are 16 sequences x 2; within one arm, mission 3 depends on mission 2. At sequence level M1 is unsafe in 12/16 sequences and M2 in 0/16; exact McNemar $p=2\cdot2^{-12}=4.9\times10^{-4}$, not $1.9\times10^{-6}$. Still significant, but report this one.
3. **P1 is evaluated where memory is right.** The 8 missions are S2.2 and S1.3. In the 8 relocation-change missions M2 is *slower* than M0 (Table S8: Q02.3 85 vs 114, Q03.2 111 vs 114, Q10.3 83 vs 113, Q11.3 74 vs 106, Q14.3 75 vs 113; the others are within ~+/-5 s). The paired-difference test over all 16 relocation missions would be about zero. The headline "114 s to 85 s" is true and pre-registered, but it must be shown next to the cost.
4. **The speed-up is bounded by the arena.** With two stations, the only thing memory can save is one search detour (about 30 s); everything else stays checked. M1age (recency-gated, never verifying) reaches 49-53 s in the model, so the "safe" variant captures about 14 of about 33 s of the available gain at $q=0$. This is a modest, honest result, and the paper should say "memory shortens missions by about a sixth" rather than imply a large speed-up.
5. **Only two stations, one geometry.** A memory with two 2-valued entries per station is almost a lookup table. Scalability is untested. Worse, Corollary 1 with $k$ stations gives $k\varepsilon$ (2.4), so the safety-versus-benefit trade-off changes with $k$, which the paper does not discuss.
6. **P3 (no extra risk) is 1 vs 0 events.** The registered criterion is "M2 $\le$ M0" with no margin. 0/32 has a Wilson upper bound near 11% and 1/32 near 16%, so P3 cannot distinguish "same risk" from "twice the risk". The text is careful ("only that it is not less safe") but the abstract and Discussion say "supported".
7. **Caution is threshold tuning.** In the model M2 and M0 have identical unsafe rates by construction (`h_change_rate.json`: 1.95 for both at $q=0.2$). Caution (memory threshold 0.01) changed the outcome of 1 of 8 fire missions where it was applied (Q09.3). That case also shows the global $\tau_h=0.05$ is simply too high for small fires: M0's 0.035 and M2's 0.049 are both far above 0.01. The study K result (4/193 false alarms at $\tau=0.0113$) says a global threshold near 0.01 costs about 2% per fire-free image in simulation. A reviewer will ask why memory is needed for that. See Fix C.
8. **Naive baseline realism.** The Discussion says the naive policy "is not a straw man" but no deployed system that skips a check is cited. Sun and Zhang (a FrozenLake study) is the only anchor. The strongest honest framing is "a stress test with a known answer".
9. **Observation 1.** It is a one-line fact about monotone Boolean conjunctions. The paper now says "elementary by design", which defuses it, but the abstract still says "We show that this bounds ...". The non-trivial content (what is actually *audited*) is only one sentence (l.275-276).

### 2.3 The $\tau_h^{\mathrm{mem}}=0.01$ inconsistency
P (frozen $\tau_h=0.05$, real photos): 64/100 false alarms. Everyday scenes score $p_h\approx0.01$ (Supp. "Study P"). On real imagery the memory caution threshold is therefore at the level of ordinary scenes: any remembered hazard would stop the robot at every view, three views per approval. The paper reports 0 false refusals in 4 caution missions of H (S4.2; upper bound about 49%) and nothing else. This is the real cost side of the invariant. The paper must at least state it.

### 2.4 Corollary 1 is not correct as stated
Corollary 1 (l.241-245): "A mission ends in at most one delivery ... Therefore $\Pr[\text{unsafe delivery}]\le\varepsilon$ for every visiting order". The premise is the per-view bound $\varepsilon$. But a mission may *visit* two stations and each may be must-refuse (wrong item at the first, fire or empty at the second; the search exists precisely for the case where the first is refused). Unsafe delivery is the union of two events, "station 1 is must-refuse and approved" and "station 2 is must-refuse, reached after a refusal, and approved", so the bound is $\varepsilon + (1-\varepsilon)\varepsilon\le 2\varepsilon$. "At most one delivery" does not remove the exposure term; it only removes it when at most one visited station is must-refuse. This is the point I made in R2 (exposure); the new text half-addresses it with a caveat but the statement is still wrong. Additionally: (a) $\varepsilon$ is measured as an average over rendered views (T1, T2), not a supremum over "every station view the robot can encounter"; for the hard class it is not small: F gives 7/13 (v3.6) and G 1/16 with look-around, so for small hidden fires the bound is vacuous without look-around. (b) the two-model and look-around rules add thresholds outside $\theta$.

### 2.5 R (degradation) and the new "supported"
`tab_r.tex`: 0/192 false approvals in every condition, including the clean reference, and 0/27 fires missed. T2 was "easy" (v3.5 already 0/407). So R degrades a set on which the check has no errors, and 0/2304 pools twelve correlated replicates of the same 192 must-refuse images. The reported world-cluster CI [0.00, 0.00]% is degenerate and will be read as a bug. An honest bound at the image level is Wilson 0/192, upper $\approx 1.96\%$, i.e. right at the registered 2% bound. It should be reported that way. R also contains none of the hard small fires (T2 has 5), where the check actually fails.

---

## 3. Feasible fixes, in days, analyses on existing data preferred

| Fix | Data | Effort | Resolves |
|---|---|---|---|
| A. Corollary 1 with exposure: $\Pr\le \varepsilon\,\mathbb E[\#\text{must-refuse stations visited}]\le k\varepsilon$; state that memory changes only the exposure term | none (text) + `h_summary.json` visit counts | 0.5 day | 2.4, N1a |
| B. Sequence-level McNemar, per-story/per-transition table in main text, label the pooled p "by design"; M2 vs M0 paired time over **all 16 relocation missions** and over all 32 | `h_summary.json`, `tab_h_sequences.tex` | 0.5 day | 2.2 (1-3), N1b |
| C. Caution vs global threshold: from existing p_h in T1/T2/G/H ledgers compute (i) false-stop rate per fire-free view at $\tau\in\{0.005,0.0113,0.02,0.05\}$, (ii) how many of the 16 H fire missions a global $\tau=0.01$ would have caught, (iii) per-mission false-stop with 3 views; also report p_h of every fire-free view M2 faced in caution mode (H ledger) | existing ledgers, study K | 1 day | 2.2 (7), 2.3 |
| D. Offline replay of M1b/M1age on H: M0 and M2 runs already contain the check outcomes at both stations; a recency-gated or look-around-only-skip policy can be replayed from those outputs and ground truth, labelled "counterfactual replay" like B0 | H ledger | 1-2 days | 2.2 (8), N1b |
| E. Break-even $q^\ast$ with a bootstrap CI over the 16 sequences, and the same model for $k=2,4,8$ stations (the exposure term scales with $k$) | `h_change_rate.json`, rates in `rates` | 1 day | 2.2 (4,5) |
| F. Non-inferiority wording for P3 ("upper bound 11% for M2 vs 16% for M0, not an equivalence claim") | json CIs | 0.1 day | 2.2 (6) |
| G. Conditional-miss analysis for the second model: $P(\text{Clef misses}\mid\text{Qwen misses})\ge15/17$, Jaccard, Wilson CI, on the 211 dev fires | `tab_i13_dev`, devset_dh_clef*.json | 0.5 day | N4 |
| H. R: report image-level Wilson 0/192 (about 1.96%), drop the degenerate [0.00, 0.00], add a sentence that T2's fires are easy; if GPU time exists, rerun R on the 16 G/F small-fire worlds (new inference, flagged exploratory) | `tab_r.tex` | 0.2 day (+GPU) | 2.5, N7 |
| I. Registration: one sentence "confirmatory within study, sequential across"; push-time or OSF/Zenodo mirror of the 13 registration files | repo | 0.3 day | N6 |
| J. ROC for P (and P2 when complete), report threshold at recall 0.95 | P/P2 outputs | 0.5 day | N2 |

---

## 4. Top 5 edits to raise the recommendation one level (borderline to weak accept)

**Edit 1. Make Corollary 1 true and give it the exposure term** (`main.tex` l.241-250, and abstract l.39-41).
Replace the statement and the first caveat with:
> **Corollary 1 (per-mission risk).** Let $k\le2$ be the number of stations a mission can check, and let $\varepsilon$ bound the probability that the memory-free check approves a must-refuse view. A verification-preserving policy delivers only after $A_{\theta'}$, hence $A_\theta$, approved the delivering station, so $\Pr[\text{unsafe delivery}]\le\varepsilon\,\mathbb{E}[N_{\mathrm{bad}}]\le k\varepsilon$, where $N_{\mathrm{bad}}$ is the number of must-refuse stations the route checks. Memory can change $\mathbb{E}[N_{\mathrm{bad}}]$ (the order of visits) but never $\varepsilon$; the memory-free robot has the same bound. We measured $\varepsilon$ for small hidden fires as 7/13 without and 1/16 with look-around (F, G), so the bound is informative only with look-around.

Abstract: replace "We show that this bounds the per-mission probability of an unsafe delivery by the per-check false-approval rate, however stale the memory is." with "Memory can change how often a check is exposed to a must-refuse station, never how often a check errs."

**Edit 2. Report H as a stress test with its limits, in the main text** (`main.tex`, Sec. V-E after "Every paired mission is listed in Supp. Table S8", ~l.480-490; Table IV; Discussion "When should a robot trust its memory?").
Insert after the McNemar sentence:
> The stories are scripted so that every transition type occurs equally often, and naive memory never verifies, so its count measures the story mix, not a rate; we therefore report the sequence-level result (naive memory unsafe in 12 of 16 sequences, verified memory in 0 of 16, exact McNemar $p=4.9\times10^{-4}$) and the break-even analysis of Fig. 5 as the evidence. Verified memory is faster only when the world persists: over the 8 persistent-relocation missions $-34$ s, over the 8 relocation-change missions $+X$ s (Supp. Table S8), and over all 32 missions the median is 73 s against 83 s. For P3, 0/32 and 1/32 unsafe deliveries have Wilson upper bounds of 11% and 16%; this shows non-inferiority only down to that resolution.

Replace "supported" in abstract l.41-43 with "supported (8 of 8 persistent-relocation missions faster; unsafe deliveries 0/32 vs 1/32 without memory and 20/32 for a naive memory)". Add the by-transition secondary table (already registered) as Table IV.

**Edit 3. State and measure the cost of caution** (`main.tex` l.221-222 and Sec. V-E, ~l.485; Limitations).
Add to Sec. III-D after the caution definition:
> Caution has a price: at $\tau_h^{\mathrm{mem}}=0.01$ the hazard question refused X of 193 fire-free views in study K (and 3 views are asked per approval), so a remembered hazard costs about Y% extra false stops per mission in simulation. On real photographs, where fire-free scenes already reach $p_h\approx0.01$ (study P), this threshold is unusable without site calibration (P2). A global $\tau_h=0.01$ would have stopped Q09.3 as well; memory's role is to apply the lower threshold only where a hazard was seen.
Add to Limitations: "We did not test whether memory-based caution beats a global threshold at equal false-stop rate."

**Edit 4. Tighten the abstract and headline claims; fill or cut TBD** (abstract, title, Table I caption, l.304-306; Sec. V-D R paragraph; conclusion).
- Title: "Verify, Look Again, Remember: A Fail-Closed Vision-Language Gate and Safe Mission Memory for Relief-Supply Robots" (two lines).
- Abstract to $\le 250$ words, one sentence per result, with the E caveat attached: "In 60 closed-loop missions with full-size fires it made 0 wrong deliveries, but on small hidden fires the same system delivered despite the fire in 12 of 13 paired worlds."
- R sentence: "pooled 0/2304 (image-level Wilson upper bound 1.96% on the 192 must-refuse images, whose fires are easy)". Remove the degenerate [0.00, 0.00]% CI.
- Table I caption: replace "Each was registered ... before its first trial" with "Confirmatory within each study; studies were designed sequentially, each after seeing the previous results (Supp. Table S7). Study C was not registered in advance."
- J and P2: fill from the registered scripts. If a result is not ready, delete the J and P2 sentences from the abstract, move them to the supplement as "pending", and cut the "registered claim \JClaim" from the conclusion. A submission with red `TBD` in the abstract is not reviewable.

**Edit 5. Demote the two-model section and give the diversity analysis** (`main.tex` l.204-212, Sec. V-F l.538-548, abstract l.47-49, conclusion).
Merge to one paragraph "Second-model veto" and add:
> On the 211 development fires Qwen3.5-9B v3.6 misses 17 and requiring Clef-Flash to agree leaves 15 misses, so Clef-Flash misses at least 15 of Qwen's 17 (88%, Wilson [66, 97]%); on T2 neither model makes a false approval (0/407), so T2 can neither confirm nor refute diversity. Clef-Flash alone (0/407, 187/193, 0.6 s) matches the pair. The claim of campaign J is therefore that the pair *fits* on one 32 GB GPU and made no unsafe delivery in 24 worlds (Wilson upper bound 14%), not that it is safer.
Remove "Jev" as a section title ("second-model role") and delete "Jev-role" in Algorithm 1.

Expected effect: Edits 1-3 close the three attacks a memory-focused reviewer will make (wrong bound, scripted p-value, cost of caution). Edit 4 removes the reviewability problem and the abstract overload. Edit 5 removes the most overclaimed contribution.

---

## 5. Other items (lower priority)
- Fig. 5 legend: "naive memory, age <= 1" should be named M1age in the legend and caption. The right panel y-axis starts at 30 s, which visually exaggerates M1's speed advantage; label it.
- Table I row H says "3 (v3.6 with no, naive, verified memory)" but P1 uses only 8 missions; state the primary endpoint per claim.
- Supp. l.157 "no threshold can separate them": change to "overlap those of the 193 fire-free T2 views".
- Fig. S5 compares p_h = 0.035 (M0) and 0.049 (M2) for the "same world" on different captures: say that view-to-view noise in $p_h$ is about this size, so the case shows noise as much as memory. A repeated-capture variance of $p_h$ for one view would show it.
- Citation spot-checks from R2 still apply to `sun2026memorylies` (verify "worse than no memory"), `chen2026clefblog` and `gihyo2026clef` (replace with the model card).
- Instruction parsing: still in the main text with 0 unsafe acceptances out of 60 and no CI; move to the supplement.

## 6. Recommendation
**Borderline** (between weak reject and weak accept), confidence 3/5.
- For: the fail-closed check with an honest negative result (5/408, target missed), a measured and fixed hidden-fire weakness (G: 11 to 1 of 16, $p=0.0019$), campaign H as a clean, audited, falsifiable stress test, mask-based labels, a registration audit, a failure log.
- Against: simulation only; the memory theory is thin and its corollary is stated with the wrong constant; H is scripted and clustered; P3 and caution rest on 1 vs 0 events; 12 studies in 8 pages with red `TBD` in the abstract (J, P2); the registrations are not externally timestamped; R's "supported" is on an error-free set with a degenerate CI.
- With Edits 1-5 (and J/P2 either completed or cut) I would move to **weak accept** for ICRA/IROS. For RA-L, a real-robot or real-image result with the site-calibrated threshold (P2) would be needed.
