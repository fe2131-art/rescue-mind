# Simulated reviewer report, round 4: docs/paper/main.tex (+ supplement.tex, numbers.tex, tab_*.tex)

Stance: critical but fair, ICRA/IROS/RA-L. Read from source only (no PDF build). Sources: `main.tex`, `supplement.tex`, `numbers.tex`,
`tab_*.tex`, `references.bib`, `experiments/PREREGISTRATION_{H,J,P2,V}.md` (L only through `git show worktree-agent-ac85b5ba081cc1f61:experiments/PREREGISTRATION_L.md`,
it is not on `main`), `h_summary.json`, `h_change_rate.json`, `h_k_scaling.json`, `g_summary.json`, and the V code (`scripts/v_predict.py`,
`h_change_rate_model.py`, `make_protocol_v.py`, `v_analysis.py`, `v_run.sh`). Pending studies (J running, P2, L, V) are judged on design only. For J
I looked only at the ledger's line count and state counts (31 runs so far, 2 FAILED, no outcome analysis). Two small CPU-light Python sensitivity runs (`nice -n 15`, 1 500-3 000 Monte-Carlo draws, no Gazebo/GPU) were used for Sec. 0 and 4.

---

## 0. URGENT (before V runs). Flaws in V's protocol, to fix before `after_l_chain.sh` reaches `v_run.sh` step (c)

V's predictions are committed by `v_run.sh` step (c), after the pilot and masks and before the first trial. Everything below can still be changed
as a registered amendment (`PREREGISTRATION_V.md` "Amendments: (none)") **if it is committed before that step**. After it, they become
unfixable post-hoc choices. If the chain cannot be edited in time, stop the chain (kill `after_l_chain.sh`) rather than let V start.

**U1. `deny_search` time is an unmeasured hard-coded default (75 s), and it drives the headline prediction.**
- `h_change_rate_model.py:rates()` falls back to `'deny_search': 75.0` ("G medians / estimates") because campaign H has **zero** `DENY_HAZARD_AFTER_SEARCH` runs
  (my count over `h_summary.json`: M0 ALLOW 9, ALLOW_AFTER_SEARCH 12, DENY_HAZARD 11; M2 12/8/12; no deny-after-search in any arm). `h_change_rate.json` confirms `"deny_search": "default"`.
  `v_predict.observed_times()` has no pool for it either, so `predict()` uses `fallback['deny_search']` = 75 s.
- V's drawn states contain 22 fire missions in missions 2-6, **15 of them with the supply relocated** (my count from `campaign_v_protocol.json`).
  In these M0 must search (wrong item first) and then stop at the fire: exactly the unmeasured path. M2 usually goes straight there (about 33 s).
  So about half of the predicted M0 - M2 saving (my estimate: 9 of 18 s) is a function of this constant.
- Sensitivity (my run, `v_predict.predict` on the drawn states without masks, deny_search overridden):

  | deny_search | predicted M0-M2, median [95% PI] |
  |---|---|
  | 50 s | 12.8 s [8.3, 17.7] |
  | **75 s (current default)** | **18.2 s [14.1, 22.5]** (matches the "about 18 s, PI 14-22" dry run in the registration) |
  | 90 s | 21.4 s [17.4, 25.2] |
  | 95 s | 22.4 s [18.5, 26.1] |
  | 100 s | 23.5 s [19.7, 27.3] |

- Evidence that the true value is about 90-96 s, not 75 s: in the E/G ledgers (`wall_s`, includes about 12-15 s of overhead relative to H's `mission_time_s`: E ALLOW 98.2 s vs H deliver_direct 83.1 s; E ALLOW_AFTER_SEARCH 124.3 s vs H 112.6 s)
  `DENY_HAZARD_AFTER_SEARCH` is 106.7 s (E, n=4) and 110.3 s (G, n=7), i.e. about 17-22 s below ALLOW_AFTER_SEARCH (no shelter drive). H's 112.6 s minus 17-22 s gives about 91-95 s.
- Consequence: a model that is otherwise exact would have its true median at **22.4 s, the upper edge of the registered interval (22.5 s)**. V1 would fail with roughly 45% probability
  for a reason unrelated to the model's structure, and the paper would then have to report "model failure" for a mis-set constant.
- Fix (30-60 min, before step (c)): (i) in `v_predict.py` build the `deny_search` pool from the 13 E/F/G runs (recompute `mission_time_s` with H's definition) plus the V pilot run VP02
  (M0, mission 2, relocated + clearly visible fire: this is exactly that path; the pilot ledger is committed together with the predictions);
  (ii) make `predict()` **raise** if a used outcome type has no pool (no silent default); (iii) record `time_pools_n` and a `time_source` per kind in `v_predictions.json`
  (the key `time_pools_n` exists, `time_source` is dropped); (iv) add the amendment text: "deny_search was previously a default of 75 s; replaced by measured pool (n=...)".

**U2. V4's first leg ("M2 unsafe <= M0 unsafe") fails by chance about 10-36% of the time even if memory is exactly as safe. The "keeps its speed-up without a safety cost" claim inherits this.**
- The model itself says each arm will have about 1.4 unsafe deliveries in 50 missions (my 3 000-draw run: E[M0] = 1.44, E[M2] = 1.45, P(M0 = 0) = 0.30).
  With independent check outcomes P(M2 <= M0) = 0.64 and P(M2 > M0 + 1) = 0.15. If the two arms tend to miss the same fires (same worlds), P(M2 <= M0) is higher but still far from 1.
  This is the same flaw as H's P3 ("M2 <= M0", no margin) that R3 flagged (R3 2.2.6), and it is now built into a new study.
- Fix: replace V4a by a margin test whose margin comes from the model: "unsafe(M2) - unsafe(M0) <= the registered 97.5th percentile of the model's M2 - M0 difference"
  (add that difference's quantiles to `v_predict.py`'s output; with the numbers above it is about 2-3), and in addition report exact paired (sequence-level) counts and Wilson bounds.
  Alternatively state V4a as "reported, not a gate". Do not leave a coin-flip as a gate of a headline claim.
- V4b (M2 fewer unsafe sequences than M1, McNemar) is nearly certain by construction (H: 12/16 vs 0/16), so it is not informative either. Keep it, but call it a replication of H.

**U3. V1 measures host load and code drift as much as it measures the model.**
- Mission time is the V1 endpoint. J's deviation note (`PREREGISTRATION_J.md`) shows check latency going 3-7 s to 25-33 s under load and page-cache thrash. V runs its arms
  as **sequential blocks** (5 missions per arm per sequence, order rotated; `make_protocol_v.py:build`), not alternated, so a load burst hits one arm.
  The paired M0 - M2 difference is a difference of two blocks run at different times.
- The time pools come from H, run on different code. Before V's first trial the chain merges I-17 (per-run layout/config files) and I-18 (operator-report hook, synchronous, inside `v32_orchestrate.py` before `stack_result.json` is written),
  both after the V registration commit `b23210f`. They are intended to be behaviour-neutral but are not listed as amendments.
- Fix: (i) amendment listing the merge commits and the "quiet host" rule (no PDF builds, test runs, other GPU/CPU jobs from the start of the V pilot to V_DONE; the same rule J had to adopt after the fact);
  (ii) log `loadavg` and `vlm_latency_s` per trial and register a sensitivity analysis excluding trials above a latency bound; (iii) add a **scale-free co-primary** to V1: the relative saving (sum M0 - sum M2) / sum M0, with its predictive interval from the same draws
  (a uniform time-scale drift cancels; an absolute 22% drift does not); (iv) a registered sanity gate comparing V's mission-1 `deliver_direct` and `deny_direct` medians to H's (83 s, 32 s): if they differ by more than 15%, V1 is reported on the relative scale only.

**U4. A silent path can delete fires from the registered predictions.**
- `v_predict.perceivable_states()` sets `fire = s['fire'] and max(design.get(w,0), design.get(w+'L',0), design.get(w+'R',0)) >= 614`. A missing mask key returns 0, so a world whose render failed
  (or whose key follows a different convention) becomes "no fire" without error. The masks file is not rendered yet (`campaign_v_protocol_design_fire_masks.json` does not exist), so this cannot be checked now.
- Fix: before computing, assert that every drawn fire mission (24 over all 60 missions, per the registration; 22 of them in the scored missions 2-6) has all three keys `V..m{k}`, `V..m{k}L`, `V..m{k}R`; hard-fail otherwise. The output already stores `n_fire_missions_drawn/perceivable`; make the run abort if "drawn" differs from the protocol's 24.

**U5. V2 as registered is nearly vacuous for two of three arms; promote the informative secondary to primary.**
- Predicted PIs (dry run) for unsafe counts: M0 [0, 5], M2 [0, 4], M1 [15, 25]. A count in [0, 5] contains almost any outcome, so V2 reduces to "M1 is about 20", which is determined by the drawn states and M1's deterministic policy, not by `p_det`.
  The model's only uncertain safety parameter (p_det = 42/44 = 95%, Wilson [84.5, 98.7]) cannot be tested with about 1.4 expected events per arm.
- Fix (a registration edit, no new runs): make **outcome-type frequencies** (deliver_direct / deliver_search / deny_direct / deny_search / deliver_skip / deny_memory, per arm; currently "Secondary") a primary test of the model's *structure* (exact multinomial or chi-square against the draws), and re-label the "model predicts" claim as "predicts structure and timing; cannot test p_det".

**U6 (minor, ops).** `v_run.sh:48` and `after_p2_chain.sh:8` write `Co-Authored-By: Claude Opus 5.5`, inconsistent with `after_l_chain.sh`, which uses Sonnet 5.5. The predictions commit is the one reviewers will look at most.
**U7 (limitation to state, cannot be changed now).** In `make_protocol_v.py` the fire is placed at the station *holding the supply* (`hazard_at = OTHER[item] if relocated else item`), so a persisting fire "teleports" whenever the supply relocates (at least V01 m2->m3, V09 m2->m3, V03 m5->m6).
No V mission has a fire at the station that does *not* hold the supply (E's "search itself must stop" case). V tests the model's process, not a physically coherent world; say so in the paper (Limitations) and in V's claim text ("under the model's change process").

---

## 1. Recommendation

**Borderline (upper half), confidence 3/5.** Up slightly from R3 (borderline, 3/5), not yet a weak accept.
With J, P2, L, V landing as designed *and* Sec. 3 fixes W2, W3, W4, W5, W7 done, I would move to **weak accept for ICRA/IROS**. For RA-L the sim-to-real gap (W1) still decides.

What changed since R3:
- Corollary 1 is now correct (union bound, k = 2): `main.tex:218-223`; the abstract states it as "number of stations checked times the per-check false-approval rate" (`main.tex:28-31`). R3 Edit 1 done.
- H is reported more honestly: sequence-level McNemar (12/16 vs 0/16, p = 0.0005, `main.tex:438-439`), "large by design" (`:439`), Wilson bounds 11% and 16% (`:440-441`), the 16 s cost when supplies move back (113 s vs 97 s, `:442`), the single case where caution mattered stated as "not less safe" (`:443`).
- Conditional-miss analysis for the second model added (Clef also misses 15 of Qwen's 17, 88% [66, 97]%, `main.tex:190`, `tab_i13_dev.tex`), so the two-model claim is demoted to "veto whose errors overlap".
- Title shortened to 3 lines (`main.tex:14`), "Jev" mostly removed (once at `:183`), Terms paragraph (`:89-95`), "scores, not calibrated probabilities" (`:149-150`), AUROC 0.96 for P (`:421`), Table I caption now says "designed sequentially, confirmatory within a study" (`:282-284`), R's per-condition Wilson bound 1.96% added (`:409-410`).
- New: study V (prediction-then-test of the repeated-mission model), study L (layouts, not yet wired into the paper), P2 and J still pending. The abstract no longer carries `\TBD` (good), but 11 lines in the body do (J, P2, V paragraphs; `\JClaim` in the conclusion `:503-505`).

Still against: simulation only; the safety bound k*eps is informative only at the point estimate (1/16 with look-around, Wilson upper bound 28%); the memory benefit rests on an assumption (persistently stale inventory) that the paper does not state; four studies are unfinished and one (L) is absent from the text; the paper is a 13-study programme squeezed into 8 pages.

---

## 2. Status of R3's weaknesses

| R3 item | Status | Evidence | What is still open |
|---|---|---|---|
| N1a Proposition overclaimed; Corollary 1 wrong by factor up to 2 (R3 2.4) | **Resolved** (statement) / open (informativeness) | `main.tex:208-228` (Observation 1 "elementary by design", Corollary with `k eps`, two caveats); abstract `:28-31`; code audit rejects thresholds above `tauh` (`:254`). | `eps` is never given a number next to the corollary. With look-around G has 1/16 (Wilson [1.1, 28.3]%) and the model uses 2/44 (upper 15%), so `k eps` is between 9% and more than 50% per mission, vacuous at the upper end. Without look-around F has 7/13. See W2. |
| N1b H is a straw man / scripted / dependent (R3 2.2.1-6) | **Partly** | Sequence-level test `main.tex:438-439`; "by design" `:439`; cost of change `:442`; Wilson bounds `:440-441`; Fig. 5 caption "model prediction" `:449-450`; all 32 missions in Supp. S8 (`tab_h_sequences.tex`). | Pooled p = 1.9e-6 still printed (`:437`). P3 headline is still "supported" (`numbers.tex` `\HHeadline`) with 1 vs 0 events and no margin (`PREREGISTRATION_H.md` P3). M1age is a model curve only, no replay on H. The benefit is conditional on a stale inventory (W6). |
| N2 P false alarms vs "fail-closed and useful"; `tau_h^mem` = 0.01 vs real-photo scale (R3 2.3) | **Partly** | Abstract `:36-38` carries 298/300 and 64/100; AUROC 0.96 (`:421`); `:443-445` compares caution with a global threshold via K (4/193 at 0.0113). | P2 still `\TBD` (`:423-427`). The text never ties `tau_h^mem` = 0.01 to P (everyday photographs already score about 0.01). `:445` says caution "caused 0 false refusals" in the "32 M2 missions"; the denominator is wrong, see W3. |
| N3 scope creep / version zoo | **Partly** | 3-line title, Terms paragraph, "Jev" gone except `:183`. | Table I has 13 rows (`:287-299`); abstract is about 328 words (target 250); 7 contribution bullets (`:59-80`) incl. "The original two-model design on one GPU". |
| N4 two-model claim | **Resolved** (analysis) / J open | `main.tex:190`; Supp. Table S9; `numbers.tex:155-159`. | J confounds model size (Qwen3.5-4B + Clef vs 9B v3.6) and prompts; its registered "no extra risk" is 0 vs 0 on 24 worlds (10 with fire). J is pending. W8. |
| N5 headline numbers stronger than they are | **Partly** | B0 removed from the abstract; Terms defines conditional denominators; `:386` "overlap those of fire-free views". | E "60/60" is still in the abstract (`:35`) without "the same system delivered despite a hidden fire in 12/13 paired worlds (F)"; `GCorrectB/C` (13/24, 23/24) are defined in `numbers.tex` and unused. |
| N6 pre-registration credibility | **Partly** | Table I caption `:282-284`; Supp. `:304-306` "confirmatory within a study but not across the programme"; C excluded `:313`; T1/G/H/T2/P2 amendment counts in `tab_prereg.tex`. | Everything is in one repo within two calendar days (`tab_prereg.tex`: 2026-10-16/17), no external timestamp. H's mechanics pilot and its Amendment 1 are not in the paper. L is absent from Table I and `tab_prereg`. W7. |
| N7 R degenerate CI; Z; hazard "probability"; H dependence | **Partly** | "scores, not probabilities" `:149-150`; sequence-level test `:438`; R per-condition bound `:409-410`. | `\RPoolCI` still prints `[0.00, 0.00]%` (`numbers.tex:138`, used at `main.tex:408-409`). R's text does not say T2's fires are easy (5/5 small ones detected), so "0/27 fires missed" cannot show degradation-induced misses. Z unchanged: CLIP refuses everything (0/191, 2/191), no non-contrastive baseline. |
| R3 minor: Fig. 5 legend/axis, Table I row H, Fig. S5 noise, instruction parsing in main | Open (cosmetic) | `main.tex:471-473` still in main body. | Low priority. |
| R3 Edit 3 (cost of caution) | **Partly** | `:443-445`. | No Limitations sentence "we did not test caution against a global threshold at equal false-stop rate" (`:490-494`). |
| New: Supp. P3 direction | **Error** | `supplement.tex:322`: "P3 compares 1 unsafe delivery (M2) with 0 (M0)". | Reversed: M0 had 1, M2 had 0 (`tab_h_arms.tex`, `h_summary.json` `unsafe_M0: 1, unsafe_M2: 0`). Fix the sentence. |

---

## 3. The 8 most important remaining weaknesses, each with a fix of at most 2 days

**W1. The only fire is a Gazebo fire; the real-image evidence is on a different task.**
Everything closed-loop (E, F, G, H, V) uses a stylised fire (flat magenta masks define "perceivable", `main.tex:266-271`); P tests the hazard question on D-Fire stills, not on the robot's view; P2 will calibrate on near-i.i.d. D-Fire train/test frames (D-Fire is extracted from video, so near-duplicates across splits are plausible) with a claim on **point estimates** (recall >= 0.90, FA <= 0.20 on 100 fire-free test images: Wilson half-width about +/-8%).
- Fix (about 1.5 days, GPU inference only, no new Gazebo trials): (a) composite real flame/smoke crops from D-Fire boxes into 200 T2/G small-fire frames at the hidden position, occluded by the existing supply mask, at 3 sizes; run the frozen v3.6 check; report miss rate against visible pixels like Fig. 4a. (b) Report the p_h distribution shift between sim fire-free views (T2, 193) and D-Fire fire-free (P, 100) (quantiles, KS), which is what `tau_h^mem` = 0.01 is really up against. (c) State P2's claim with the Wilson bound, not the point estimate; discuss the leakage risk.
- Effect: removes "stylised fire only" as the main objection for ICRA/IROS; necessary (not sufficient) for RA-L.

**W2. The central safety number, eps for the hardest class, is based on 16 fires, and R never stresses that class.**
G: 1/16 missed with look-around (Wilson upper 28%), model p_det = 42/44. F: 7/13 without. The corollary's k*eps is therefore 12.5% at the point estimate and not informative at the upper bound. R covers 27 T2 fires that are easy (T2 small fires 5/5, `numbers.tex` `TTRefSmall`), so "0/27 missed under 12 degradations" says nothing about hidden fires.
- Fix (about 1.5 days): an image-level replay of G. The look-around decision is a pure function of the three captures (front, +/-0.4 m), so render 150 new small-hidden-fire worlds x 3 design poses with the T1 generator and mask labels (perceivable if >= 614 px in any view), apply v3.6 +/- look-around offline, and get eps with a CI of about +/-3% instead of +/-20%. Then run the same 150 worlds through R's 12 degradations (about 5 400 inferences).
- Effect: turns the paper's key number from "one miss in 16" into a tight interval, and gives R teeth. This is the single most convincing addition.

**W3. Memory-based caution is never compared with a global threshold at equal false-stop rate, and its cost denominators are wrong.**
The only decisive caution event is Q09.3 (M0 p_h = 0.035, M2 = 0.049, `main.tex:443`). Both are above the conformal threshold 0.0113 of study K, so a *global* tau_h = 0.0113 would have stopped M0 as well, at 4/193 = 2.1% false stops per fire-free view (about 6% per approval with 3 views). `:445` says caution "caused 0 false refusals" in the "32 M2 missions". Per `h_summary.json`, caution applied in 12 of the 32 M2 missions, but only **4** were fire-free (Q04.2, Q06.2, Q08.2, Q09.2), so the evidence is 0/4 (Wilson upper 49%).
- Fix (0.5-1 day, analysis of existing ledgers): for tau in {0.005, 0.0113, 0.02, 0.05} compute fires caught (G 16 + H 8 + E fire worlds) and false stops per fire-free view and per mission (T2 193, G 8 fire-free, H, E); plot against the single operating point of memory caution. Report the same per-station false-stop rate in V (caution applies in V's fire-gone missions, so V gives more data: register it as secondary).
- Effect: either shows memory caution is a free lunch on stations with history (strengthens a core claim) or honestly demotes it to "equivalent to a local threshold". Removes R3 2.2.7/2.3 for good.

**W4. "Supported" is asserted for inequalities with no margin on one or zero events.**
H P3 (M2 <= M0: 0/32 vs 1/32, Wilson upper bounds 11% and 16%, `numbers.tex:174-175`), the planned V4a (U2), J's "unsafe J <= A" (0 vs 0 likely), and R's "supported" at a 1.96% bound against a 2% criterion. The supplement reverses P3's direction (`supplement.tex:322`). `\HHeadline` = supported is then used in the abstract and the conclusion (`main.tex:503`).
- Fix (0.3 day, text and one script): add a "claim status" column to Table I with three values (met as registered / met and informative / not met), and for each non-inferiority endpoint print the exact upper bound of the difference (e.g. M2 - M0 in unsafe missions: conditional exact bound on the discordant pairs). Rename P3 "met as registered; informative only down to about 11-16%". Fix `supplement.tex:322`. Drop `[0.00, 0.00]%` (`numbers.tex:138`) from the R sentence.
- Effect: removes a class of "overclaim" comments; costs nothing in content.

**W5. There is no empirical comparison with the closest prior mechanisms; the novelty claim is textual.**
`main.tex:101` lists differences from VAP-TAMP and KnowNo but no baseline is run. Reviewers will ask whether paraphrase voting (VAP-TAMP) or conformal option sets (KnowNo) already give the same false-approval rate.
- Fix (about 1 day, image-level GPU inference on T1, T2, dev): (i) VAP-TAMP-style: five paraphrased yes/no questions per fact, majority vote, no permutation agreement; (ii) KnowNo-style: split-conformal prediction set over {water, medicine, other} from q1 alone (calibrated on dev), refuse unless the set is a singleton equal to the request; (iii) report false/correct approvals, hazard recall and AUROC next to Table II. Study K already supplies a conformal tau_h; extend it to p_s.
- Effect: converts "we differ in X" into "X matters (or does not)". Either result is publishable; the absence of any is the first thing a specialist reviewer will write.

**W6. The memory speed-up is conditional on an assumption the paper never states: the inventory stays wrong.**
Fig. 5 and the k-station formula (`main.tex:455-458`, `h_k_scaling.json`) assume the supply sits away from the inventory station in about half of the missions (`h_change_rate_model._run`: `reloc` starts Bernoulli(0.5) and toggles with q, so its stationary value is 0.5). M0 then needs 1.5 visits per mission (`h_k_scaling.json`: `visits_M0 = 1.5`). The robot's own operator report asks the operator to "update the inventory" (`main.tex:159-161`); once the operator does, M0's search disappears and memory's saving with it. The honest headline is also smaller than the abstract's "114 s to 79 s": the model gives 14.1 s at q = 0 (M2) against 53.0 s for naive memory (`h_change_rate.json` `break_even`), i.e. verified memory captures about 27% of the naive saving at q = 0 and none at q = 0.5.
- Fix (1 day, model and text): add the probability that the inventory is stale at the start of a mission (and an operator-correction rate) to `h_change_rate_model.py` and to the saving formula (saving = delta * P(inventory wrong and memory right) ...); show the saving for P(stale) in {0.1, 0.5, 1}; replay M1age on the H and V ledgers as a labelled counterfactual (R3 Fix D); state the "27% of the naive saving" number in the abstract or Sec. V-E as the price of safety.
- Effect: pre-empts the "straw-man speed-up" objection and gives the memory contribution a quantitative, defensible core.

**W7. The evidence base is still in flux, one study is not in the paper, and registration remains self-hosted.**
J, P2, L, V are pending; `main.tex` has 11 lines with pending macros (J `:462-469`, P2 `:423-427`, V `:460`, conclusion `:503-505`). Study L (24 layouts, `PREREGISTRATION_L.md`) runs tonight but appears nowhere in `main.tex`, `supplement.tex`, `tab_prereg.tex` (grep for "layout"/"study L": 0 hits) and its preregistration is only on an unmerged branch. L's design is fair but note two things for the text: the feasibility constraints keep every leg 0.6 m clear of objects because the controller has no obstacle avoidance, so L shows generalisation of the *check and audits* to layouts with free straight paths, not of navigation; and it contains no small hidden fires, so it does not touch the weak point.
- Fix (0.5 day): wire L now (Table I row, one sentence, macros with `\TBD` fallback, `tab_prereg` row), define the "freeze" order (V, then regenerate numbers, then delete or move every study that is still pending), deposit the registration files and a release tag with an external timestamp (Zenodo or Software Heritage), list H's mechanics pilot and Amendment 1 in Supp. S9.
- Effect: reviewability. A submission whose conclusion contains `\TBD` cannot be reviewed.

**W8. Too many studies for 8 pages, and the second-checker contribution adds length but not safety.**
Table I has 13 studies; the abstract has about 328 words and nine headline numbers. J's endpoint P2 ("unsafe J <= A") is evaluated on 24 worlds of which about 10 contain a fire (about 0.5 expected misses for v3.6): it cannot differ. P1 ("fits on one V100") is a VRAM measurement that does not need 24 closed-loop worlds. J's arm also changes the model (4B vs 9B) and the prompts, and both J failures so far occurred in arm J (`ledger`: 2 FAILED, both J).
- Fix (0.5 day, text only): drop the "original two-model design" bullet from the contributions (`main.tex:68-69`), reduce Sec. III-C and V-G to one "Second-model veto" paragraph (feasibility: peak VRAM, latency, 0 extra unsafe deliveries, with the overlap statistic), move Z, K, R's table and instruction parsing to the supplement, cut the abstract to <= 230 words and three numbers per contribution. Keep Table I as the claim-status table (W4).
- Effect: from "a programme" to "two questions with answers", which is what a conference reviewer reads in the first five minutes.

Expected cumulative effect: W2 + W3 + W4 + W5 turn the three largest technical objections (is the number small? is caution needed? is it different from prior work?) into measured answers; W7 + W8 make the paper reviewable and focused. That is borderline to weak accept. W1 (and P2) is what separates weak accept from accept at RA-L.

### Pending studies judged on design
- **J**: sound as a feasibility check, weak as a safety claim (above). The loaded-host deviation is honestly documented. Report latency as two parts and not as a property of either configuration (already planned).
- **P2**: the procedure is sensible (calibration constraint first, then lower FA; tie goes to the deployed wording). Risks: near-duplicate D-Fire frames across splits; a claim on point estimates with n = 100 negatives; Amendment 1 changed the calibration draw from two shards to all nine (documented, before any inference, acceptable). Report Wilson bounds and ROC points, not only the chosen operating point.
- **L**: fair test of layout generalisation of the check and the audits; threshold 22/24 and 0 unsafe is reasonable; limitations as in W7. Its largest value would be the secondary time-versus-path-length fit.

---

## 4. Study V: prediction-then-test of the repeated-mission model

**Is it sound?** The idea is the right one and it is rare: predictions are computed from rates measured in other studies (G, H), conditional on the drawn world states and the design fire masks, committed and pushed before the first trial, and the run stops if the commit is missing (`v_run.sh` step (c) plus the `merge-base` check; an uncommitted file makes `git log -1 -- file` empty, which fails the check, so the ordering guard works). The change process in V is not scripted, which answers "scripted stories decide the headline". Arms share the seed mission and worlds, order rotated, labels as in H.

**Is the predictive interval constructed correctly?** Mostly yes, with the exceptions in Sec. 0:
- Correct: parameter uncertainty enters through Beta posteriors on p_det (42/44) and p_fs (0/60, posterior Beta(1, 61)), shared across arms within a draw; check outcomes and mission times are random; the policy logic mirrors `_run`; quantiles by index into sorted draws (20 000 draws, Monte-Carlo error negligible); the paired difference is computed within draw, so it reflects the common p_det; memory seeding is shared across arms as in the protocol; "refusing to overwrite" protects the registered file.
- Wrong or fragile: (U1) the unmeasured `deny_search` constant; (U4) silent deletion of fires; (U3) no time-scale uncertainty (PI half-width is only about +/-4 s on 18 s, narrower than a 10-20% drift in host speed); no failure handling (a failed run shrinks the observed pair count but not the predicted denominator, `v_analysis.py` V1 vs `predict`).
- Known model gaps, which are *model* failures if they show up (so acceptable, but write them down before the run): no caution false-stop term (M2 applies tau_h^mem = 0.01 on fire-gone stations; the model uses p_fs for them, estimated at 0/60 under tau_h = 0.05); an imperceptible fire is relabelled "no fire" while the robot may still stop on it (counted as false refusal at rate p_fs, probably too low); check outcomes for M0 and M2 are drawn independently although both see the same world (this widens the PI for the paired difference, so it makes V1 *easier* to pass, which should be disclosed); M1 can end in an absorbing refusal state (memory never updated after DENY_MEMORY), which H never showed for more than 2 missions and V can show for up to 5 (check that the real memory code does the same: `mission_memory.py`; my reading of `h_summary.json` is consistent with it).

**Are V1-V4 well chosen?**
- V1 (observed mean M0 - M2 inside the registered PI): right quantity, but needs the fixes U1 and U3 and a scale-free co-primary.
- V2 (each arm's unsafe count inside its PI): weak (U5). Replace or supplement with the outcome-type frequency test.
- V3 (Wilcoxon over 10 sequence means, median > 0, p < 0.05): reasonable, high power only if most sequences contain a relocation. In the drawn states V02 has no relocation or fire at all (its mean difference is noise around 0, dropped by `wilcoxon_exact` if exactly 0) and V04/V08 are persistent. With about 6 relocation toggles in 50 transitions (expectation 10) the detour cost is observed in few missions; report the realised toggle counts.
- V4 (M2 <= M0, M2 < M1): see U2. V4b is not informative.

**Missing from V:** (i) a pre-registered statement of what V cannot test (p_det, fires at the station not holding the supply, real-world change processes); (ii) a rule for stack failures that stops them biasing V1 (exclude the whole pair, and report the number); (iii) a null-model comparison: does V1's PI discriminate? E.g. report the predicted M0 - M2 under a model with q = 0 or with no memory benefit and show the observed would be rejected by it; this makes "the model predicts" falsifiable rather than "an interval contains the observation".

Net: V is a good idea whose current version has two defects that would produce spurious failures (U1, U2) and one that would hide spurious passes (U5). All are fixable in an afternoon.

---

## 5. Novelty versus closest prior work

- **VAP-TAMP** (Oloo et al. 2026, `references.bib` `oloo2026vaptamp`): paraphrased yes/no VLM questions with a majority vote, active perception when the view is insufficient, vote updates the state used for replanning. Our look-around is a restricted instance (two fixed side views, may only revoke); the real differences are (a) closed-set next-token scoring with permutation agreement versus voting, (b) a fail-closed conjunction instead of a vote, (c) the velocity guard, (d) the audit. No experiment separates (a)-(b) from VAP-TAMP's mechanism (W5).
- **KnowNo / conformal** (Ren et al. 2023): next-token scores over options with a coverage guarantee and human help. We use thresholds chosen on development data and refuse; the conformal threshold is only an offline add-on (K), and exchangeability is broken by design (27% vs 7% small fires). So we do not offer KnowNo's guarantee for the supply decision, only an empirical rate.
- **Memory papers**: ReMEmbR / KARMA / ConceptGraphs-style memories answer or plan; Sun and Zhang show stale memory hurts in a grid world; GLOVE and VLM-DEWM check memory against fresh observations. Closest in spirit is GLOVE (verify memory against the environment), so "memory proposes, perception disposes" is a design principle that has near neighbours in cache revalidation ("conditional GET"), Simplex-style monotone shields and trust-but-verify agents.

**Is "memory may only reorder and add caution" publishable?** As a theorem, no: Observation 1 is a one-line fact about monotone conjunctions, and the paper says so, which is to its credit. As a design rule with a measured price it is a small but real conference contribution, provided the price is quantified: verified memory captures about 27% of a naive memory's time saving at q = 0 (14.1 of 53.0 s) and nothing at q = 0.5, in exchange for the memory-free risk. The more original and sturdier result in the paper is the hidden-fire / viewpoint finding (G: 11 to 1 of 16, exact p = 0.0019) with its failure analysis and the audit method; I would let that carry the title and the abstract and present memory as the second result.

**What would make it stronger** (in order of value):
1. A **risk-budgeted** policy instead of a binary one: verify with probability rho(age), derive the Pareto frontier of time versus unsafe deliveries between M1 and M2 (M1age is one point on it), and show where a stated risk budget puts the robot. This turns "never skip" from a dogma into the endpoint of a trade-off curve and answers "why not skip when the memory is one mission old?".
2. A **wrapper theorem plus one demonstration on an existing memory system** (e.g. a ReMEmbR/ConceptGraphs-style memory proposing stations or objects): any memory-conditioned planner is made verification-preserving by routing its proposal through the same check. The claim then is generality, not the toy memory.
3. **Larger k and real change statistics**: a 4-station sim (L's layout code makes this feasible) and published change rates (semi-static mapping data such as FreMEn's) to replace the free parameter q.
4. W2: a tight eps. Without it the safety side of the contribution is a sentence, not a number.

---

## 6. Writing: the 10 places that most hurt clarity

1. **Abstract, `main.tex:24`** "Running the full stack exposed two gaps, and we close each with a simple, verifiable rule." ("close" is contradicted by G's remaining miss and by H.)
   Rewrite: "Running the full stack exposed two gaps. We address each with a simple rule that can be audited."
2. **Abstract, `main.tex:28-31`** one 60-word sentence carrying the memory rule, the bound and "however stale".
   Rewrite: "Memory may only change the order of the stations and make the hazard threshold stricter; it never removes a check. An unsafe delivery then needs a false approval by the same check a memory-free robot uses, at no more than two stations per mission."
3. **Abstract, `main.tex:34-38`** "Every evaluation was pre-registered ... against \ZSigTOneFA{} for a zero-shot SigLIP baseline" (overclaim: C was not; chained design; nine numbers in four lines).
   Rewrite: "All studies but one were registered before their first trial, and every closed-loop trial was audited against simulator ground truth. The check made 3 false approvals on 408 must-refuse held-out images (zero-shot SigLIP: 44) and none in 2 304 degraded-camera tests."
4. **Introduction, `main.tex:55-58`** two questions in one sentence plus "Our answers are a system design and an evaluation methodology".
   Rewrite: "We ask two questions. First, can an off-the-shelf VLM gate a delivery so that it rarely approves a wrong one? Second, can a robot's memory shorten repeated missions without weakening that gate? We answer both in simulation, with audited, pre-registered experiments."
5. **Contribution bullet, `main.tex:68-69`** "The original two-model design on one GPU ... We fill the second checker's role with Clef-Flash, which Cloudflare post-trained from Qwen3.5-9B" (project history, not a contribution).
   Rewrite: "A second model as veto. Clef-Flash may veto an approval; we test whether the pair fits on one 32 GB GPU (campaign J)."
6. **Sec. III-C, `main.tex:183-184`** "The original design of this robot asked two models (a second checker, called Jev in that design, and Qwen) ..."
   Rewrite: "Optionally, a second model, Clef-Flash, is also asked and the robot moves only if both models approve."
7. **Memory theory, `main.tex:213-216`** "Let eps bound the probability ... The bound must hold for every station view the robot can encounter." (a supremum assumption stated, an average measured).
   Rewrite: "Let eps be an upper bound on the probability that the memory-free check approves a must-refuse view. We estimate eps as a rate over rendered views (Sec. V), so the corollary is a statement about that estimate, not a guarantee."
8. **Sec. V-E, `main.tex:434-445`** one paragraph of about 400 words and 15 macros, with the headline in a subordinate clause ("The registered headline claim ... is \HHeadline.").
   Rewrite: split into (a) design, (b) results table pointer, (c) cost, (d) the Q09.3 case. Headline sentence: "P1 (faster when the relocation persists, 8 of 8 missions) and P2 (20 vs 0 unsafe) hold. P3 (no more unsafe deliveries than no memory) holds as registered with 0 vs 1 events, which does not show equivalence."
9. **`main.tex:443-445`** "Caution is cheap because it is local ... in the 32 M2 missions this caused \HFalseReftwo{} false refusals." (wrong denominator.)
   Rewrite: "Caution applied in 12 of the 32 M2 missions, but only 4 of these were fire-free; it caused 0 false refusals in those 4 (upper bound 49%), so its cost is not established."
10. **Discussion, `main.tex:482-483` and conclusion `:497`** "Moving beats thinking harder ... (T2, whose fires were easy, cannot rank models on safety)" and "Three lessons carry beyond our arena."
    Rewrite: "On our small hidden fires, moving (G) removed more misses than a better prompt with crops (F); we did not compare against a larger or second model in closed loop, because T2 was too easy to rank them." and "We draw three observations that we expect, but did not test, to transfer beyond this arena."

Also: `main.tex:151-152` "a false alarm only stops the robot" contradicts P (64% false alarms is an availability cost); change to "a false alarm costs availability (Sec. V-D shows how much on real photographs)".

---

## 7. Checklist of concrete edits (for the author)

- Before V: U1-U5 (Sec. 0). Highest value per minute: U1.
- `supplement.tex:322` swap M0 and M2 in the P3 sentence.
- `numbers.tex:138` / `main.tex:408-409`: remove the world-cluster `[0.00, 0.00]%` from the R sentence; keep "0/192 per condition, Wilson upper 1.96%" and add "T2 fires are easy".
- Add a Limitations sentence: no equal-false-stop comparison of memory caution with a global threshold (until W3 is done), fires follow the supply in V, benefit conditional on a stale inventory.
- Wire L (Table I, `tab_prereg`, one sentence) and list H's pilot and Amendment 1 in Supp. S9.
