# Simulated reviewer report, round 6 (restructured paper): `docs/paper/main.tex` on `i21-depot` (b2b2b45)

Stance: hostile but fair, RA-L / ICRA reviewer with a security background. Read from source and from the built PDFs
(`main.pdf` 9 pages including 1.5 pages of references, `supplement.pdf` 17 pages; both build cleanly with the `rescuemind:latex` container; 43 `TBD` tokens
are visible in the main PDF). Sources: `main.tex`, `supplement.tex` (S10 proof, trust base, threats), `numbers.tex`, the previous round
`REVIEW_NOTES_R5.md`, and the protocols `experiments/PREREGISTRATION_{A,X,XD,S}.md` (DRAFT, in the i21 worktree), `_V.md` and `_W.md` (registered, on main) and
`_Q.md` (commit c7d06b3, branch `worktree-agent-ac893207bdda069d9` only; no inference yet). Judged on design where results are pending (A, S, V, W, Q, X, XD).

---

## 0. Verdict (Japanese, short)

**判定: R5 の borderline から一段上がった (構成の問題はほぼ解決)。A/S/V/W/X/XD が設計どおりに出れば、RA-L で weak accept 圏 (主観 50-55%)、ICRA/IROS 40%、セキュリティ会場 15%。**
**残る主な問題は結果ではなく、(i) 主張の言い回しが設計の検出力を超えていること、(ii) ε の定義が防御側の視点 (F/L/R) に依存していること。**
主要 study が失敗した場合の床: 「型付き tighten-only インタフェース + 大きい (正直な) ε の実測 + 失敗を残す方法論」。RA-L 25-30%、実質ワークショップ水準。
致命的になるのは次の 2 つだけ: (a) 閉ループで Prop. 2 の反例 (監査が通るのに ε で説明できない unsafe 配送)、(b) oracle steering で k=4 の ε_any が大きく、「保証」が空になる。
ε が大きい / τ_h が動く / 防御が効かない、は設計上「主張しない」側に置いてあるので、書き方次第で論文は生き残る。

**貢献を 1 文で引用するなら (レビュアが書くであろう文)**:
> "Advice (memory, peers, inventory, operator text) may only reorder checks or tighten thresholds, never remove one, so the risk of an unsafe delivery under any advice is capped by the gate's own measured error budget; the authors measure that budget, its price in time and refusals, and the one channel (scene text) the rule does not cover."

その直後にレビュアは「原理は古い (Biba, CaMeL, Fides, algorithms with predictions)、命題は 1 行、経験的な中身は ε と価格だけ」と続ける。
貢献は「構造」ではなく「構造 + 測定 (ε, 価格, 監査) + 失敗の記録」と言い切れる形に書くのが安全 (§2)。

---

## 1. Verdict in detail: all pending land as designed vs the key ones fail

### 1.1 If A, S, V, W, Q, X, XD land as designed
* **RA-L**: weak accept (about 50-55%). The chain is readable in one pass (Fig. 1 does the job), the evidence is closed loop and audited, failed claims are kept, and the limits paragraph is honest.
  What still costs points: simulation only (the abstract does not even say "simulation", §5), 8-16 pairs per closed-loop study, one group registering its own studies in its own repo, and a main result that is large by construction (M1 20/32 unsafe).
* **ICRA/IROS**: borderline (40%). The panel will ask for something on a real robot, or at least real camera frames through the gate; Q, XD-R and P2 are real *photographs*, image level, one component each.
* **Security venue**: weak (15%). The principle is old, the interface is 60 lines, the adversary is a fixed authored set; the adaptive adversary (steering) is under-powered (§4.1), and S is non-adaptive.

### 1.2 The paper's floor if the key studies fail
Ranked by how much each failure would hurt:

| Failure | Consequence | Survives? |
|---|---|---|
| Monotone audit fails, or an unsafe delivery in A/X that gate error does not explain (a counterexample to Prop. 2, e.g. through a non-static frame, §3.1 P1) | The headline is false | No. Fix the rule or the assumption; the only truly fatal case |
| Oracle-steered ε_any (§3.1 P2) is large at k=4 (XD/W) | The relative guarantee is correct but empty in the depot; "guarantee" becomes a word | Partly. Re-title around "a relative bound and its measured size" |
| W: look-around Wilson upper bound > 0.15 | Link 3 weakens; k·ε̂ about 0.2-0.3 at k=2 | Yes (the paper already says "small, not zero") |
| XD: ε not tight, τ_h moves, smoke-only worst | "Absolute ε does not transfer" is exactly what the paper pre-states | Yes, and a good result if reported as designed |
| A-steer shows no effect (expected: 1 event in 16) | Nothing learned (power about 0, §4.1); must not be sold as "order does not matter" | Yes if worded "not detectable, upper bound x" |
| S: defences do not close the vulnerability | The paper already says scene text is outside the guarantee | Yes |
| V: model misses its interval | Reported as a model failure, as registered | Yes |
| Q: supply check does not transfer to photos | Reported; already known for the hazard question (P/P2) | Yes |
| X: unexplained deviations | Protocol says it blocks the depot sentence | Yes (depot sentence dropped, 0.5 page back) |

**Floor claim set that survives any outcome**: (i) a typed tighten-only interface whose monotonicity is machine-checked and audited against ground truth; (ii) naive memory/advice fails and the price of
the safe version is measured in seconds and refusals (by construction, but measured with an audit); (iii) a measured, large-ish ε with an honest interval and a look-around that reduces it (G, W);
(iv) a record of registered claims that failed. That is a methodology + negative-results paper at about 25-30% for RA-L; the depot, the S defences and Q decide whether it reaches 50%.

---

## 2. Is the chain argument coherent now? One quotable sentence

**Yes, mostly.** Gate (fail-closed) -> hidden fires dominate ε -> look again lowers ε -> advice may only tighten (ε is the budget) -> outside the guarantee. Fig. 1, the abstract and the title now say the same thing.
The R5 complaint "five parallel contributions" is fixed. Residual incoherences a reviewer will still find:

1. **Link 3 is rhetorical, not logical.** Prop. 2 holds for any ε; "look-around makes ε small enough for the bound to mean something" is not what the bound needs. And the bound is *not* small: k·ε̂ = 0.125 at k=2 (upper 0.57) and vacuous at k=4, which the paper says itself.
   Either (a) change the link to "advice adds nothing to ε, so reduce ε; look-around is the tool we measured" (no "meaning" claim) or (b) replace Σ ε_s by the policy-independent ε_any (§3.1 P2), which is measurable and not vacuous.
2. **Link 5 mixes two different things**: scene text is an attack channel outside the guarantee; the depot is an external-validity test. "Outside the guarantee: scene text and realism" makes realism sound like an attack surface.
   Split it (5 = scene text, measured; limits of validity = depot / photographs), or title the section "Outside the guarantee and outside the arena".
3. **Link 2 rests on 3 false approvals** (T1: 3/408, all from the 48 correct-supply visible-fire images). "Dominated by hidden fires" is true but is a statement about 3 events; say "all 3".
4. **The chain shows pending evidence at links 3 and 5** (W, A-steer, S, X are `TBD`). Fine now; a reviewer reads a pending claim as an unproved link, so keep Fig. 1's "pending" tags until the freeze and delete them after.
5. **The quotable contribution appears twice with different words**, in the abstract ("may only reorder visits or tighten thresholds, never remove a check") and as contribution (i). Use one sentence verbatim in the abstract, the intro and the conclusion.
6. **Contributions (ii) look-around and (iii) audited evaluation do not follow from the title.** Keep them as "two supporting results", not as co-equal (the abstract already does this; the intro list does not).

---

## 3. Residual technical holes: Prop. 2, cost bound, audit, trust base

### 3.1 Proposition 2 (and its definitions)
* **P1. The frame-independence assumption is stronger than "static world" and is false in two places you already use.**
  The proof needs `o_s` not to depend on the visiting order. (a) *Arrival pose depends on the route*: W/XD draw the arrival error from the spread measured in the arena's F/G/H runs; in the depot (aisles, k=4, obstacle) the approach path, and hence the pose distribution at a bay, depends on the previous bay, so `ε_s` is a function of the predecessor, and an advice-chosen order changes the pose law an attacker can induce.
  (b) *The depot has a moving smoke emitter* (main text, Sec. VI-D), so the world is not static and a later visit sees a different smoke phase. Fix: define `ε_s` as the sup over predecessors / arrival-pose laws and visit times, or measure it per predecessor in XD; say that the depot's emitter violates "static world" and that the bound then holds only for the stationary distribution.
* **P2. The sum is the wrong quantity.** An unsafe delivery implies the event `E = ∃s: M_s(w) ∧ A_θ(o_s)=1`, whose probability is `ε_any ≤ min(1, Σ ε_s)`. `ε_any` does not depend on k, order or advice, can be estimated directly (every station of every world, offline; W/XD need no extra renders), and is *attained* by an oracle steerer when duplicate supplies exist.
  State the proposition with `ε_any` and keep Σ as a corollary. This removes the "vacuous at k=4" admission, turns A-steer from a 16-world demonstration into a measurement (§4.1), and answers the security reviewer's "bound is loose" in one line.
* **P3. Conditional vs unconditional ε.** The definition in Sec. III-B is a probability over the *world distribution*; the number plugged in (G: 1/16) is conditional on the hard class (small hidden fire present). That is a safe upper bound but must be said: write `ε(class)` and state the proposition per class, or multiply by the class prior.
* **P4. The attacker does not control the world in the threat model, but ε is an average over generator worlds.** A per-world statement is impossible (the check is nearly deterministic given the frames). A physical adversary who picks fire geometry, lighting or an occluder has `ε_adv(N) ≈ 1-(1-ε)^N` over N tries. Either declare the world adversary out of scope in one sentence, or add a cheap random search over fire parameters (about 200 renders, offline) and report the best-of-N miss rate.
* **P5. Label dependence: "perceivable" is defined by the defence's own views.** M_s (and the unsafe label in G, H, V, A, W, X, XD) counts a fire only if at least 614 px are visible in F, L or R, which are the poses look-around uses. Look-around's success on "perceivable" worlds is partly definitional, and a fire hidden from all three views (the real residual hazard) is *excluded from ε by construction*.
  Cheap mitigation: (i) report in the main text the share of hard-class fires *not* perceivable in any of F/L/R (W's "imperceptible fire worlds" is only secondary) and what the check does on them; (ii) add the six-view label (W Amendment 1 already renders it) as the leading secondary analysis; (iii) for XD add an extra ring of 4-6 views used for labels only. Also: Fig. 3a says fires under 2 000 px are missed by every configuration, but the perceivable threshold is 614 px, so the labelled class includes 614-2 000 px fires that the model cannot see from any pose.
* **P6. Notation.** `Pr[unsafe | a]` conditions on a fixed advice set, but the bound is over the joint law of `(w, a(w))`. Write `Pr_w[unsafe under a(w)]`.
* **P7. The requested supply `s*` is parsed from the same operator text that carries advice**, and M_s is defined relative to `s*`. A text that flips `s*` (not only the destination) delivers an item that is "right" for the parsed request. The threat table lists the destination parse as outside Prop. 2; list the supply parse too, with its offline number (intent accuracy).

### 3.2 Cost bound
* **C1. δ is a simulation number.** 4/193 at τ about 0.0113 on simulated fire-free views, against 64/100 flagged at the frozen 0.05 on real photographs (P) and a calibrated τ of 0.35 (P2). The supplement says "a statement about the arena"; the *abstract and Sec. IV "Price"* still say "bounded availability". Give the bound as a function of δ (`1-(1-δ)^v`) and print δ per site (arena about 2%, depot XD-3, photographs P), or add "at the simulated per-view false-alarm rate" to the abstract.
* **C2. Scrutiny is not in the bound.** Scrutiny adds three views (two at 0.8 m, one 0.3 m closer) at every advice-promoted station, which an attacker can force every mission with a truthful location item. The bound `(k-1)W` covers reordering only. Price scrutiny in seconds (X-s measures it) and write the per-mission cost as `(k-1)W + s_scrutiny`.
* **C3. Persistence and flooding are named but not bounded.** A peer that writes hazard records for every station each mission, or re-sends truthful location advice every mission, costs per-mission cost times missions with no cap (S10 (iii) admits it; provenance with decay is "unevaluated"). The abstract's "costs bounded availability" will be read against that. Cap it (one non-own caution active, decay after one mission; one unit test, 0.5 day) or write "per mission" in the abstract.
* **C4. Soft refusal is not free when the supplier is unique.** In the 2-station arena soft refusal cannot recover (protocol A, A3 note); "hazard advice costs a visit instead of the mission" holds only with a clean duplicate. Say so next to the claim.
* **C5. Independence in `1-(1-δ)^v`.** δ is measured on images of different worlds; the three views of one world are correlated through lighting, so the independent value (0.118) is optimistic. Use the `3kδ` form (0.124) in the main text.

### 3.3 The audit
* **A1. Two audits, only one supports the claim.** The main text now says so ("What the evidence is"); keep it, and add that the *outcome* audit relies on simulator ground truth, which exists nowhere outside the simulator: the empirical content is "in simulation, with the labels as defined".
* **A2. The "independent" reference implementation, the mutation tests and the fuzzing were written by the same authors (indeed the same AI assistant) from the same specification.** "All injected bugs are killed" is a statement about the suite's power against the authors' imagination. Say "second implementation by the same authors from the same specification" and, if possible, have a person not involved write the 60-line oracle from the one-paragraph rule (1-2 hours; the cheapest real independence available). The same applies to **Q's label audit** (performed by the AI that wrote the study); spot-check 10% by a human before inference.
* **A3. Registration is a commit in the authors' own repository.** `git merge-base --is-ancestor` proves order only if history cannot be rewritten. An external timestamp (a signed tag mirrored to Zenodo/OSF, or the registration hash in a public issue) takes an hour and removes the standing objection. A, X, XD and S are still DRAFT: do it when they are committed.
* **A4. State the audit's power in the main text** (e.g. "10 of 10 injected faults detected; 5 real bugs found"), not only that it ran.

### 3.4 Trust base
* **T1. The 60-line `advice.plan` is the *specification*, not the TCB.** The mission node, which also implements the naive baselines behind flags, must honour the plan (consult `A_θ'` before delivery, never take a skip branch). Table "Trust base" lists "mission gating ... the ROS wiring (reviewed)": "reviewed" is the weakest cell in the paper, and the audit is *testing* of this wiring on sampled runs, not verification.
  The paper already has the right pattern for motion (the independent velocity guard). **Add a delivery interlock**: a tiny separate node that lets the "deliver" action through only if it has seen a signed approval record (image hash, scores, rule version) for the delivering station in this mission. That moves "mission gating" out of the weak cell into a roughly 40-line component with the guard's property, and makes "Obs. 1 is enforced in code" literally true. Effort 1-1.5 days including tests.
* **T2.** List the model allow-list hash in the TCB table ("a model not on the allow-list" is a fail-closed claim that rests on it); the "server that lies consistently" and the sensor path are correctly listed as not covered.
* **T3. Same-host assumption.** VLM server, node, recorder and audit run on one machine and the audit trusts files written by the node under test. Acceptable for a research artefact; put it in the TCB table, not only in S10.

---

## 4. Do the pending designs support the claims as worded? (power, baselines, adaptive attacker, transfer)

I read the draft and registered protocols against the sentences in `main.tex` that depend on them. **[BEFORE] marks changes that must be made before A, S, X, XD are registered**; after the commit they are amendments.

### 4.1 A (226 runs)
* **[BEFORE] A-steer cannot test steering at n = 16.** The prediction is `unsafe(monotone) ≈ ε_hard ≈ 1/16`, so the expected count is one world; a one-sided sign test needs at least 5 discordant (P(≥5 | ε=0.06) about 0.2%). The most likely outcome is 0 or 1, i.e. "not significant". The paper then says (Sec. VI-C): *"If monotone is not worse than the control, advice-chosen order did not matter."* That reads absence of evidence as evidence of absence (0/16 has a Wilson upper bound of 0.19).
  *Wording*: "no steering effect was detectable in 16 worlds (upper bound x); the image-level oracle-steered ε_any (W/XD, n about 130 / about 100) is the estimate". *Design (free)*: add an offline, no extra GPU secondary to W and XD: pair each fire world with a clean duplicate and score "oracle steering" (the attacker picks the station the check approves wrongly) = ε_any of §3.1 P2. That is the steering number at 10x the sample size.
* **[BEFORE] The "adaptive attacker" is one truthful tip authored by the defenders.** It is adaptive to the *rule* but not to the *world or the model*; a real adaptive attacker would query the check offline. The oracle-steering analysis is the honest version; the closed-loop cell then demonstrates cost and mitigation (scrutiny, soft refusal), not an effect size.
* **[BEFORE] "A fire visible only from the extra poses counts as no fire (conservative for the unsafe count)"** (A, Labels). That makes the unsafe count *smaller*: it favours the headline and is unfavourable only to scrutiny's cost. Reword, and report both labels (design-mask only and six-view), as W Amendment 1 does.
* **[BEFORE] A1 and A1b compare against baselines built to be beaten.** The naive arm has a skip semantic by definition; the filter is the *same* 9B model with one yes/no question (no independent guardrail, no attack search against it); there is no agentic-LLM baseline that decides for itself (R5 #7, not done). With 12 world pairs A1b cannot go below p = 0.031. Wording: A1 is a "design-space demonstration (the interface, not the model, decides)", not a safety test; call the filter "self-filter" and say that no independent guardrail or adaptive attack on it was tried. Keep the McNemar p out of the abstract.
* **Abstract**: "an advice-following baseline made X unsafe deliveries and ours Y" is fine once labelled "by design"; the number a careful reader wants is *ours versus the no-advice control* (exposure), so print that beside it.
* A2 (6 pairs, all must agree) is a deterministic geometric effect; fine as descriptive.

### 4.2 S (64 worlds, six arms)
* **[BEFORE] "closes the vulnerability" (D1/D2) is a claim about non-adaptive signs only.** The attacks were authored before the defence and none is built to evade the OCR detector (small, low-contrast, curved, printed on the object, off-axis); an OCR mask is evaded by construction by anything it does not read. Add a small *detector-aware* sign set (about 12 worlds, variants chosen to be missed by the detector on development renders) or reword D1/D2 to "reduced on a non-adaptive sign set". The main text must carry the same qualifier; today it does not mention the defences at all.
* **[BEFORE] Occlusion is silently dropped.** "Pairs whose label changes with the sign are excluded": a sign that hides the fire from the mask is a *real* attack (the cheapest one). Count it as its own category and report it.
* **[BEFORE] D-safety (the defence itself blanks the fire and creates a false approval) is "reported, not a criterion".** A "cheap" defence that turns a refusal into an approval is not acceptable; make zero new false approvals on no-sign must-refuse worlds part of "closes at acceptable cost".
* **Power**: 6-10 worlds per sign type; H1's "0/9" has a Wilson upper bound of 0.30; H3/H5 hinge on counts of 1. The registration says p-values are descriptive: keep them out of the main text, which currently lists eight rates. Reduce the S paragraph to pooled flips with intervals plus the defence verdict.
* **Table I and S12 are stale**: "52 worlds ... 4 systems (ours, one pass, free-form, full image)"; the protocol has 64 worlds and six arms (adds OCR-MASK, IGNORE-TEXT and the legitimate-label control).
* One VLM, one font, large high-contrast signs. Samarakoon et al.'s "0% in 5 400 trials" is the strong prior; S neither replicates nor contradicts it; say so in one line.

### 4.3 X (80 runs) and XD (1 284 images plus ablation)
* **[BEFORE] The paper's depot sentences promise things X does not run.** Table I ("H and A arms, A-steer"; "M1 vs M2 vs M0"), Table IV ("Unsafe M0/M1/M2 ... depot: TBD / TBD / TBD; ordering: yes"; "A: unsafe naive/ours") and the abstract ("in a cluttered four-station depot the arms ordered as TBD") all expect an M1 arm and naive advice at k=4. The X protocol explicitly **does not re-run M1 at k=4** ("Known limits") and its advice cell has control / monotone / scrutiny only. Rewrite to what X measures: M0 vs M2 (safety, time, visited bays, stale-proposal price at k=4) and the steering cell. Otherwise the depot claim is "not delivered" on day one.
* **[BEFORE] X-s has at most 8 fire worlds**; the protocol says so and registers no test. The main text (Sec. VI-D) says steering "is meaningful (k ≥ 3 ...)": meaningful as a design, not as a test. Say "descriptive; the finding is the availability cost of a truthful tip".
* **K2 "prediction not rejected" is weak**: the prediction is computed with perfect perception on the very sequences that are run, so it tests the navigation and perception of the stack, not a model, and a cluster-bootstrap CI over 4 sequences is a low bar. Word it "consistent with", not "confirms k-scaling".
* **[BEFORE] XD's registered "transfer" claims include tautologies.** O1 (look-around misses are a subset of front misses; the McNemar test is a sign test on a subset relation) and O3a (adaptive ≤ look-around, "always true by construction") cannot fail; W-a1 is the same. A claim that cannot fail does not confirm transfer. Replace with effect-size claims that can fail (for example "look-around removes at least half of the front-only misses"), or report them as descriptive counts.
* **[BEFORE] XD-ε is under-powered for the class that matters.** `tongues_small` has 28 worlds; 0/28 has a Wilson upper bound of 0.12 and 1/28 of 0.18, so "upper bound ≤ 0.15" passes only with at most one miss, while the pooled criterion hides the hard class behind `tongues_big`, `mesh_flame` and `sprite`. Either raise the small/hidden pool to about 100 worlds (roughly +0.8 h render and scoring) or register the claim on a pooled hard class (all small/hidden appearances, about 50) and state it per class.
* **XD-R measures false alarms only.** At a lenient depot τ*, a threshold that flags little passes "FA ≤ 0.20" trivially; add recall of real fire/smoke at the same τ* (P2's D-Fire test images exist) so the claim has both sides.
* **Transfer is within the same simulator.** The depot is third-party geometry; the fire, smoke, sprite and mesh are authored by the same group ("never tuned on a model score" helps, "no co-adaptation" cannot be shown). Say "scene-distribution shift within Gazebo", and reserve "sim-to-real" for Q, P2 and XD-R at image level.
* "An unexplained deviation blocks the depot sentence" (X) is a good rule; pre-specify the cause taxonomy so that one navigation stall in 80 runs does not delete half a page.

### 4.4 V, W, Q
* **V**: Amendment 1 widened V4 to "M2 − M0 ≤ the 97.5th percentile of the model's distribution (3 in the dry run)". That is a *weak* safety criterion, so "verified memory keeps its speed-up **without a safety cost**" (Sec. VI-B; conclusion "H: supported") overclaims. Word it "M2 had at most 3 more unsafe missions than M0 in 50 (bound), against x for naive". V1/V2 compare the authors' model with the authors' simulator: say "model and simulator agree", not "the model predicts reality".
* **W**: good design (150 fire worlds, 75 twins, registered criteria, nothing tuned). W-a1 is a subset test (see above); keep W-a2 (upper bound ≤ 0.15) and W-a3 (≤ 10% false stops) as the claims. With n about 130 and true ε = 6% the expected upper bound is about 11%, so the criterion is passable but not assured; be ready to write "ε about 0.10". The six-view label and the imperceptible-fire count are the interesting numbers: promote them to the main text (§3.1 P5).
* **Q (supply check, 405 Commons photographs)** is nowhere in the paper (not in Table I/S12, `numbers.tex`, abstract); "all 19 studies" is now 21 with Q and XD. Add one sentence to the "outside the arena" paragraph and a row to S12. Wording: labels were audited by the AI that wrote the study (state it; human spot-check), the audit removed unclear images, the claim needs both E1 (upper bound ≤ 0.05) and E2 (≥ 0.70). It tests one component on photographs, not a robot; it cannot support "gap to real sites".

### 4.5 Cross-cutting wording
* The abstract's "**the gap to real sites [is] measured**" is an overclaim. What is measured: the hazard question on D-Fire photographs (P/P2), the supply check on Commons photographs (Q), false alarms on warehouse photographs (XD-R). No robot, no real fire dynamics, no real camera pipeline. Say "measured at image level on public photographs".
* The abstract never says the evaluation is **in simulation**; add "in Gazebo" to the first results sentence.
* "Pre-registered" means a commit by the same authors: add "time-stamped in the public repository" plus an external anchor (§3.3 A3).
* "Moving beats thinking harder" (Discussion) rests on G/W against F/T2 failures that sit in the supplement; add the pointer.

---

## 5. Presentation: figures, tables, abstract, title

* **Title.** "Advice May Only Tighten: Untrusted Inputs to a Fail-Closed Vision-Language Gate on a Relief Delivery Robot" is memorable and states the rule. Two caveats: (i) "Delivery Robot": there is no grasping or handover, "delivery" is arrival at the shelter; "relief logistics robot (in simulation)" is truer; (ii) the title promises a rule, not a guarantee, which is accurate: keep. Reviewers punish titles that hide "simulation" more than titles that state it.
* **Abstract (about 215 words).** Good: one chain, four results. Fix: (a) "in simulation"; (b) `20 of 32 ... ours 0` is by construction (scripted stories): lead with M2 vs M0 and G, and put the disclosure in the same sentence ("naive memory, which fails by design in 20 of 32 ..."); (c) "the arms ordered as TBD" is not a result sentence: after results give one number (time saved, unsafe count with bound) or delete; (d) "the gap to real sites ... measured" (§4.5); (e) "bounded availability" (§3.2 C1); (f) the last sentence "Failed registered claims are reported" is the most distinctive thing in the paper: put the count in it ("four of N registered claims failed").
* **Introduction.** The chain list uses study letters (E, T1, G, W, H, V, A, S, X) that mean nothing to a first-time reader: use names in the sentence and the letter once in parentheses. The three-bullet contribution list restates the abstract: shrink to two supporting results.
* **Figures.** Fig. 1 (the chain) is the best figure; its box text is `\scriptsize` at full width: check it at print size. Fig. 5 (H case, 1/3 page) is a nice qualitative figure about one sequence: move it to the supplement and use the space for the **missing headline figure**: unsafe deliveries (Wilson bars) against mission time for M0/M1/M2 and the advice arms (naive, filtered, monotone, scrutiny), from real data. It replaces the circular consistency-robustness model curve in the supplement with the empirical one. Figs. 3b and 4 show the same thing; one can go.
* **Tables.** Table II (studies) is `resizebox`ed to a tiny font with 7 rows x 6 columns; cut "Data" and "Arms" to the supplement and keep Study | Question | Primary endpoint | Claim status. Table IV (arena vs depot) is the right idea and good form ("Transfers?" stated in advance), but its M1/naive cells are cells X does not produce (§4.3).
* **Placement.** Table II lands at the top of p. 6, far from the Methods paragraph that cites it; Table IV is on p. 7, far from Sec. VI-D. `[t]` plus a few `\FloatBarrier`s (placeins) fix both.
* **TBD handling.** 43 `TBD` tokens in the PDF; make the build fail on `\TBD` after the freeze (R5 #8): a `\freeze` switch that turns `\TBD` into a `\PackageError`.
* **Length.** 9 pages including references (body about 7.5): fine for RA-L; no room for the headline figure without moving Fig. 5.
* **Study count.** "all 19 in Supp. Table S12" and "not the nineteen" in Methods are now wrong (Q and XD exist).

---

## 6. Top-8 fixes, ranked by value / effort (Japanese)

| # | 修正 | 工数 | 期限 |
|---|---|---|---|
| 1 | **登録前の言い回し凍結 (A/S/X/XD/V)**: A-steer の「order は無関係」を「検出不能 (上限 x)」に; X の M1/naive-advice 参照 (Table I/IV, abstract) を M0 vs M2 + steering の記述統計に; S の「closes」に「非適応的サインに対して」を付ける; XD の O1/O3/W-a1 (部分集合で自明) を claim から降ろし反証可能な効果量 claim に; V4 の「safety cost なし」を「M2−M0 ≤ 3」の境界つき表現に。 | 0.5 日 | **A/X/XD/S を commit する前** |
| 2 | **Prop. 2 の再定式化**: Σε_s ではなく政策非依存の ε_any (= P[∃s: must-refuse かつ承認])、クラス条件つき ε、k に依存しない。W/XD に **oracle steering の ε_any** を画像レベルの二次解析として追加 (GPU 追加ゼロ)。A-steer の検出力不足 (n=16, 期待 1 件) を n 約 130 に置き換え、k=4 の「vacuous」も解消。 | 0.5-1 日 | W を採点する前 (W は未実行) |
| 3 | **ラベルの循環を断つ**: 「perceivable」を防御側の F/L/R で定義している。6 視点 (W Amendment 1) を主要な二次解析に、**どの視点でも見えない火の割合**を本文に出す。XD は label 用の追加リング、`tongues_small` を 28 から約 100 に (または小/隠れクラス合算を登録)。614 px と、2000 px 以下は誰も検出できない (Fig. 3a) 点も明記。 | 1 日 | XD を commit する前 |
| 4 | **Prop. 2 の仮定を直す**: 「フレームが訪問順に依存しない」は、到着姿勢 (経路依存) と depot の動く煙で崩れる。ε_s を前の拠点・訪問時刻について sup で定義するか、XD で前拠点別に測る。ε_adv(N) (火の配置 best-of-N 探索、約 200 render) を 1 行足す。 | 1 日 | XD の設計時 |
| 5 | **TCB を小さくする**: 配送インターロック (署名つき承認記録が無ければ「deliver」を通さない小さな別ノード; 速度ガードと同じ型)。「mission gating = reviewed」を弱点から外す。独立参照実装は「同一著者・同一仕様」と正直に書き、可能なら第三者に 60 行の oracle を書かせる。scrutiny の時間と持続的 DoS (provenance + decay) を cost bound に入れる。 | 1.5 日 | 結果の凍結前 |
| 6 | **abstract / タイトル / intro の過大表現**: 「シミュレーション」と明記; 「gap to real sites measured」→「公開写真で画像レベルに測定」; 「bounded availability」→「シミュレーションの δ で」; M1 の 20/32 は「by design」と同じ文に; 研究数 19→21 (Q, XD) を Table I・S12・Methods に反映し Q を 1 文で入れる; 失敗した登録 claim の数を最終文に。 | 0.5 日 | 随時 |
| 7 | **S の防御評価を強くする**: detector-aware なサイン (約 12 world)、サインによる火の遮蔽を「除外」でなく攻撃の 1 カテゴリとして数える、D-safety (防御が新たな誤承認を作らない) を criterion に、本文 S 段落は 8 個の率でなく pooled flips + 防御 verdict に、主表の S 行を 64 world / 6 arm に更新。 | 1 日 | S を commit する前 |
| 8 | **信用性の仕上げ**: 登録の外部タイムスタンプ (署名タグ + Zenodo/OSF、約 1 時間)、Q ラベルの人手 10% 抜き取り、`\TBD` が残るとビルドが失敗する仕組み、ヘッドライン図 (unsafe vs 時間の Pareto, 実データ) と Fig. 5 (H の事例) の入れ替え、Table II の列削減、float 配置。 | 1 日 | 凍結時 |

**順序 (今日 2026-10-17、締切 2026-11-02、GPU は静かなホスト 1 台で全 study 直列、約 38 GPU 時間)**:
1 → 2 → 3 (W/A/X/XD/S の commit 前; 文章と軽いコードだけ) → W → A (A-steer を先に: 3 時間枠) → XD → S → X → Q → 4, 5, 6, 7, 8 (結果待ちの間に並行)。
1-3 は commit 後だと amendment になるので最優先。5 は最も価値の高い堅牢化だが他と独立なので結果待ちの時間で行う。

---

## 7. Things that are good and should not be touched

* The one-chain structure, the tighten-only rule stated as a rule (not as "robustness"), and Fig. 1.
* The "Relative, not absolute" paragraph and the exposure / steering honesty: unusually candid for this literature and the strongest reply to a security reviewer.
* Reporting failed registered claims (T1's 2% bound, F, T2, J) and the registration audit table.
* Stating what should and should not transfer (Table IV, XD) before the depot data exist.
* The "What the evidence is" paragraph separating the advice audit (finds bugs) from the outcome audit (supports safety).
* S placed outside the guarantee with an explicit no-structural-claim statement; V as predict-then-test; W as a 10x larger image-level replacement for the 16-world G.
