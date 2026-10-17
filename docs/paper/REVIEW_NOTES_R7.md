# Simulated reviewer report, round 7 (theory of Prop. 2 necessity and Prop. 3 advice credit): `docs/paper/main.tex`, `supplement.tex` on `i21-depot` (5984bbb)

Stance: hostile but fair, RA-L / ICRA program committee, robotics + security. Read-only review: no LaTeX build, no Docker/Gazebo/GPU, no test suite (a timing-sensitive experiment is running).
Sources read: `main.tex`, `supplement.tex` (S10 in full: probability space, A1-A4, Prop. 2 + proof, Sharpness, Necessity, cost bound, Prop. 3 + proof, tightness, related work), `numbers.tex`, `references.bib` (credit keys),
`REVIEW_NOTES_R6.md`, `LITERATURE_I24.md`, `rescuemind/advice.py`, `rescuemind/advice_credit.py`, `rescuemind/advice_llm.py` (how items reach the ledger), `scripts/v32_orchestrate.py` (settlement),
`ros/gazebo_waypoint_mission.py` (where `caution_refusals` is written), `tests/test_i24_advice_credit.py`, and `experiments/PREREGISTRATION_{A,B,IF,S,X,XD,V,W,Q}.md`.
The only code I executed is a few lines of pure-Python calls into `advice_credit.py` (`nice -n 19`, milliseconds, no model, no ROS) to confirm the counterexamples in Sec. 2; the sequences are given so that they can be turned into unit tests.

---

## 0. Verdict (Japanese, short)

**判定: 構成と主張の言い回しは R6 から大きく改善 (R6 の「登録前に直す」項目はほぼ反映済み)。ただし今回の新しい理論 2 つに穴がある。**
(1) **Prop. 2 の十分条件 (tighten-only ⇒ ε_any 以内) は正しい**。しかし **Necessity の「if and only if」は、述べられた形では正しくない**: 前提「どのフレームも安全を証明しない」が最終文から落ちていて、しかもその前提自体が (信頼できる証明書つきの緩和を除外するための) 強い仮定。「q > 残りの予算」は循環した書き方 (正しくは q > ε0/(1+ε0))。「only kind of interface」と本文で言い切るのは言い過ぎ。
(2) **Prop. 3 (advice credit) は、コードに対して述べられた形のままでは成り立たない。確認できた反例が 4 つ** (Sec. 2): (a) 重複供給で「正直な再配置」が +1 返金されるため、実際には 1 訪問も節約していないのに嘘を 2 回に 1 回ずつ許す (40 ミッションで無駄訪問 20 回、真の節約 0 のとき論文の式は 12); (b) `source` は助言ファイルの項目が自己申告するラベルで、1 つのファイルが 4 アカウントを使えるため、**40 ミッション全部が無駄訪問** (信用は無力化); (c) 既定 (soft refusal なし) では hazard 側は一度も課金されない (`caution_refusals` は `--caution-soft` でしか書かれない)、(d) 認証済みピアの口座は `advice.validate` が `peer_id` を捨てるため到達不能 (コードに死んだ分岐)。さらに scrutiny 由来の誤拒否と、実際に燃えている局への「正直な」誘導 (配送を失う) は課金されず、むしろ返金される。
安全性 (Prop. 2) は無傷: 信用は項目を落とすだけなので。壊れるのは「価格」の主張だけで、修正は小さい (口座のスタンプ、返金の廃止または再定義、hazard の課金を `pre_caution_reason` から、約 1 日)。**修正するか、主文の limits の「credit で有界」を一文に縮めて補遺に回すべき。** 締切 2026-11-02 まで 15 日。
**採択確率 (主観)**: 現状 (A/S/V/W/X/XD/Q/B が未実行、`\TBD` 55 個) で **RA-L 約 40%、ICRA/IROS 約 28%、セキュリティ会場 約 12%**。主要 study が設計どおり出れば RA-L 50-55%。今回の理論の穴を放置して査読者に反例を見つけられると、「機械検査された保証」という最大の売りが傷つくので、-5 から -8 ポイント。修正すれば Prop. 2/3 は強みになる (+3 から +5)。
最も効くのは (i) 保留中の study を実際に出し切ること、(ii) credit/necessity の穴を塞ぐか縮めること、(iii) 主張の整合 (抄録の「k に依存しない」など)。

---

## 1. Correctness of the new theory

### 1.1 Prop. 2 itself (sufficiency): correct under A1-A4, with two wording defects

The proof is pointwise in omega: delivery from a must-refuse s needs A_theta'(o_s)=1 (A3); the supply conjunct is unchanged, V ⊆ V', p_h < tau_h' ⇒ p_h < tau_h, so A_theta(o_s)=1 on the same frames (A1); hence omega in E. Boole gives the sum. No problem with clairvoyance or adaptivity. Sharpness (naming j*(omega) first attains eps_any) is right; the plan accepts a reorder to any station when the base's first station is the catalog one. Two defects:

* **A4 is self-contradictory as worded**: "w is independent of the advice; the adversary may be any function of omega". If advice is a function of omega, it is not probabilistically independent of w. What is meant is causal: advice cannot change w, xi. Write "advice does not influence (w, xi)". (R6 P6 notation point is also still open: `Pr[unsafe delivery under a]` with a = a(omega).)
* **Lemma 1 treats V as a set of poses; the adaptive rule (I-20) makes the realised view set depend on the frames.** The argument still goes through (A is a conjunction, and scrutiny's six views ⊇ any adaptive subset, a smaller tau_h' only turns "suspicious" views into refusals), but the lemma should say "for every realisation of the frames, the views taken under theta' contain those taken under theta". One sentence.
* **Abstract vs S10 contradiction.** The abstract says eps_any is "independent of the visiting order and of k"; S10 says (correctly) that eps_any "weakly increases with the station set". It is independent of the *order and the advice*, not of the site or k. Fix the abstract.

### 1.2 Necessity: the "iff" is not correct as stated

What is argued: take a relaxing interface (exists a*, o* with A_theta'(a*)(o*)=1 but A_theta(o*)=0). *Suppose no frame certifies safety* (every frame is produced by some must-refuse world). Put mass q on a world whose must-refuse station produces o*, and send a* exactly when o* is captured. That world adds q to the unsafe rate and nothing to eps_any; pick q larger than the rest of the budget. Conclusion: "under A1, A3 and A4 the bound holds for every advisor and every generator law iff A_theta'(a)(o) ⇒ A_theta(o) for all a, o".

Findings, in order of severity:

1. **The "Hence ... if and only if" sentence drops the premise.** The iff holds under A1, A3, A4 *and* the no-certificate premise (call it N), and A3 as written is one-directional ("delivers only if approved"). The unsafe event also needs the converse: an approval at the first-named station leads to a delivery (liveness). Without N the "only if" direction is false: an interface that waives the hazard conjunct when a trusted certificate says "no flame-coloured pixel in any of the six views" (or a hardware interlock, or a signed record from a verified source) is *relaxing* by the definition, yet cannot add must-refuse mass if the certificate is sound. So "Tighten-only is the *only* kind of interface for which such a bound can hold" (S10) and "The condition is also necessary" (main Prop. 2 text, which does not mention N at all) overstate. Correct claim: *for advice that conveys nothing the check can verify (every frame it could relax is producible by a must-refuse station), tighten-only is necessary.*
2. **N is stronger than the argument needs, and false as written.** The construction uses a single frame o* that is refused by the check and producible by a must-refuse world. It never uses "every frame". At the level of raw frame tuples (all six views) the premise is false: a clean tuple (right supply, no fire in any view) is not producible by a must-refuse station (M_s requires a perceivable fire in a design view or a wrong supply, both visible in the tuple), and the paper's own false-alarm frames (4/193 at tau about 0.0113) are of this kind. The meaningful version is over the *check's observable summary* (scores and labels), where it is plausible but unverifiable. The sentence "this is the operational meaning of a check with eps > 0; it errs because frames are ambiguous" does not follow: eps > 0 says some must-refuse frames are approved, not that refused frames are ambiguous.
3. **"q larger than the rest of the budget" is circular as written.** The budget is a function of q: eps_any(new law) = (1-q) eps0, so the condition is q > (1-q) eps0, i.e. q > eps0/(1+eps0) (at most 1/2). Say it that way. Also: the construction needs the generator law to be free to put an atom on one world. That is legitimate for the "for every law" quantifier, but it means the result is "no *law-free* bound", not "any relaxing interface is unsafe for the deployed law"; with the real law the extra mass is q* = Pr[must-refuse and refused and in the relaxed set], which may be small. This is the honest, quantitative form and it is stronger than an iff:
   **Decomposition (suggested replacement).** Let R(a) = {o : A_theta'(a)(o)=1, A_theta(o)=0}. Under A1, A3 (+ liveness), for a clairvoyant advisor Pr[unsafe] <= eps_any + eps_rel, eps_rel = Pr[exists s: M_s and o_s in R(a)], with equality for the best advisor; the bound by eps_any for all laws holds iff no frame producible by a must-refuse station lies in R. For naive skip, R contains every refused frame, so eps_rel is about Pr[must-refuse and refused] = (1 - eps) of the must-refuse mass (this is what A measures). This is a calculation, not a characterization claim, and it cannot be attacked by "your premise is false".
4. Not trivial, not false for the intended class: the construction is a valid worst-case argument, and "naive/filtered are relaxing, so no such bound exists for them" is correct (skip relaxes every refused frame). A filter indeed only shrinks the set of a* that get through. Keep that sentence.
5. Quantifier slip: "for every relaxing interface there is a generator law and a clairvoyant advisor" is fine; the final "for every advisor and every generator law" must say that eps_any is that of the same law (it is, implicitly).

### 1.3 Proposition 3 against `advice_credit.py`

Facts about the code that the proof uses and that hold: admission reserves worst_cost (1, +0.25 with scrutiny) per item against the pool, greedily per (source, pool) within a mission; `advice.plan` applies at most one reorder per mission; the charge for a reorder is at most 1.25 <= reservation; credit is clamped at 0 and capped at C; hazard regenerates by rho per mission; the shadow refund is at most once per source and mission; `settle` rounds to 9 decimals (the 1e-9 admission tolerance cannot accumulate to anything that matters). Credit only drops items, so Prop. 2 is untouched. The *literal* inequalities "debit <= C + refund + shadow" and "shadow <= rho_s m" are what the property test checks, and they hold. The problems are in what the quantities *mean*, and in who the "source" is.

**V1. "n_saved" is not the number of saved visits (refund without saving). Confirmed counterexample to Prop. 3(a) and to the "net price <= C + rho_s m" sentence.**
`settle` refunds REFUND_LOC=1 whenever the advised station's own check found the supply (`supply_match is True`). With a duplicated supply (the depot, k=4; the A-steer worlds) the inventory's first station also holds it, so the reorder saved 0 visits but is refunded 1. A peer alternates: odd missions a false location claim (wasted visit, charge 1; credit 2 to 1), even missions a true claim to a duplicate-holding station (confirmed, refund 1, credit back to 2). Run through the real `plan_with_credit` / `settle` (k=2 style outcomes, alternate truth is a confirmed non-wasted reorder): **20 wasted visits in 40 missions, true visits saved = 0**, against the paper's C_l + n_saved + rho_s m = 2 + 0 + 10 = 12. The bound as proved holds only if n_saved is read as "number of confirmed reorders" (which can exceed the visits really saved by the number of ties). So: (a) must be restated with n_conf; (b) the "net price in visits <= C_l + rho_s m" statement (docstring, S10 text, and B's registered secondary "theorem") is false when duplicates exist; with scrutiny the same trick also makes the truthful-but-useless source pay S=0.25 every mission uncharged (the refund -1 + 0.25 is net negative, credit sits at the cap). B2 (honest, k=2, single copy) cannot see this.

**V2. The accounting identity ("source = channel") is attacker-controlled. Confirmed, and it makes the throttle vacuous.**
`advice.validate` keeps the item's own `source` field (any of memory/peer/inventory/operator); `plan_for_mission` loads the peer file with `adv.load` and never stamps a channel; `source_key` returns that label. One poisoned file listing the same lie under four labels gets four accounts. With four false "supply at the other station" items and four true redundant ones: **every one of 40 missions wastes a visit** (the four shadow refunds add 1.0 credit per mission, which pays one lie per mission for ever). That is exactly "no credit". The S10 Sybil paragraph guards against free *peer ids* but the free label is one level lower. Fix: stamp `source` from the channel in `plan_for_mission` (file path / extractor), ignore the item field for accounting (30 minutes plus a test).

**V3. The hazard pool is never charged in the default configuration. Confirmed by reading the code path.**
`visits_from_mission` sets `refused_base = refused and station not in caution_only`, and `caution_only` comes from `mission['caution_refusals']`, which `ros/gazebo_waypoint_mission.py` writes only when `--caution-soft` is on (`soft_front = soft and front_caution_only(...)`). Without soft refusal a hazard item can cause a caution-only refusal (a lost delivery, the *expensive* case), but the record has `refused=True, refused_base=True`, charge 0. So Prop. 3(b) holds vacuously (the counter that is bounded is always 0) and hazard flooding in the default stack is unpriced. The information needed is already in the decision (`pre_caution_reason` is written by `mission_memory` in both modes; `caution_soft.front_caution_only` shows how). Fix: classify caution-only from the decision, not from the soft-refusal log (30 lines plus tests). The registered B does not exercise hazard advice, so B cannot catch it.

**V4. Costs that are not charged, and some that are refunded.**
* A truthful location claim to a station that really burns (the A-steer attack): the hazard stop loses the delivery; `supply_match` is computed from the two passes' supply answers regardless of `allow`, so the reorder is **refunded**. The cost-bound paragraph (i) itself calls this the dominant cost, and the credit mechanism treats it as free.
* Scrutiny-induced false refusals (6-view caution threshold at the advised station): the reorder is confirmed (refund), the caution-only refusal is not charged to any pool (only items with effect `caution` hit the hazard pool). A truthful source with scrutiny on causes about 6 delta-bar of lost deliveries per mission, uncapped.
* An undecided check at the advised station is charged 1 even when the cause is a *real* hazard (supply fields absent): honest sources that point at a burning bay are penalised while the same claim with a readable supply is refunded. Inconsistent direction of the error.
* Settlement is skipped when the run has no `mission.json` or the audit failed (`v32_orchestrate`): the plan was admitted but never charged, and regeneration does not tick. Prop. 3 quantifies over settled missions only; say so (A5: every mission is settled).
* Total price across channels: per-source bounds sum over up to four channels (and unboundedly many certified peers), so "the price of a persistent liar is capped at C_l" is per channel; with V2 fixed the global bound is 4(C_l + rho_s m) visits. State it.

**V5. Certified peers are dead code.** `advice.validate` returns `{source, kind, station, text}` and drops `peer_id`, so `source_key(item, ledger)` never sees it through `plan_with_credit` (checked: items with `peer_id='p1','p2'` and a ledger with both certified end up in the single account 'peer', one admitted, one throttled). The unit test calls `admit` directly with items that still carry `peer_id`, so it passes. The paper's sentence "a peer gets its own account only if the operator certified its identity" describes behaviour that is not reachable. Safe direction (more throttling) but an honest certified peer is throttled for an uncertified liar's behaviour.

**V6. Tightness remark (floor(m/(L+1))).** For the stated strategy (L=ceil(1/rho_s)=4 confirmed truths, then one lie) the count floor(m/5) is right (0.2 m). It is not the worst case, and the rate term is tight in a stronger sense than the paper claims: in the lie mission the source adds a second, *throttled*, true claim (for example "supply at the inventory's own station"; the plan rejects it as "no reorder needed", but the shadow check still refunds 0.25 because the robot's recovery visits that station). The credit then goes 1 to 0 to 0.25 in the lie mission, so a lie costs 4 missions, not 5: **11 wasted visits in 40 missions = 2 + floor((m-2)/4) (checked)**, against the bound 2 + 0.25 m = 12. So the bound is not violated, the rate is 0.25 not 0.2, and the claim "any rule that re-admits after L confirmations can be exploited at the same rate" should read 1/L. Also: the shadow refund is granted for an *uninformative* claim (a true statement about the station the control visits anyway), i.e. it pays for confirmations that carry no information. A better shadow rule pays only when the claim named a station the inventory order would not have visited first. The descriptive model's "adaptive liar" (295 s against 1 533 s for the always-liar, 19%) is the greedy one; this attack reaches about 26% of missions and the label attack (V2) 100%, so Fig. `credit` understates the worst case; plot the best known attack and say so.

**V7. Minor.** Credit pools are initialised lazily per key (a new key starts full; fine for four fixed channels, not for unbounded ids). A missing ledger file is "fresh, full credit": whoever can delete or redirect the file resets the bound; the paper says only that a corrupt one fails closed. The registered B mechanics gate runs k=2, location only, one label: it tests wiring, not V1-V5.

**Suggested statement of Prop. 3 that is true of this code after V2, V3 fixes:** per channel c, (a) wasted visits (actual extra visits against the no-advice order) <= C_l + n_conf + rho_s m, where n_conf counts confirmed reorders; the *net* statement (<= C_l + rho_s m) holds only for single-copy supplies; (b) caution-only refusals charged to hazard items <= C_h + rho m, with the charge defined from the decision, plus the scrutiny and hazard-stop terms listed explicitly. The cleanest repair is to **drop the full refund** (confirmed reorder charges 0, not -1), add time regeneration rho_l to the location pool, and keep a smaller shadow rule: then (a) is C_l + (rho_l + rho_s) m with no n_saved at all, the net statement is true with or without duplicates, a truthful source is never debited (consistency (c) unchanged) and V1 disappears. Add the scrutiny cost to a separate time budget instead of the visit pool.

### 1.4 Cost bound (S10 (i)-(iii)) and related work
* "At most one extra station check (<= W)": correct in count; in *time* the reorder changes the drive legs as well, W is a median, not a worst case. Say "at most one extra visit".
* Hard refusal and lost delivery are priced in the text but not in Prop. 3 (V4); the paper's main Limits sentence ("the price of advice repeated over many missions is [bounded] by a per-source credit that only drops advice") therefore overclaims until V1-V4 are fixed or the sentence is narrowed to location visits in single-copy settings.
* Related work paragraph: the (sigma, rho) regulator framing (Cruz 1991) is exact and honest; the learning-augmented references are correctly described as within-instance competitive-ratio results. Bib entries look right; `antoniadis2023mixing` is an arXiv-only `@misc` (consistent with the literature note); `chen2026paging` is an arXiv June 2026 preprint, so cite as preprint and keep "recent work". One conceptual caveat to add: a (sigma, rho) regulator assumes charges are measured by the regulator; here the charge is measured by the robot's own check, which is why V1-V4 (what the check *can* observe) matter more than the algebra.

---

## 2. Concrete counterexamples (for unit tests)

All with `rescuemind.advice_credit` defaults (C_loc=2, rho_shadow=0.25, refund 1, no scrutiny), through `plan_with_credit(..., 'monotone')` then `settle` with a hand-built visit list; arena item `water`, catalog station `water`, other station `medicine`.

* **CE-1 (refund without saving).** For m=1..40: odd m: items `[loc(peer, medicine)]`, visits `[medicine: supply_match False, water: True]` (a lie, a wasted visit); even m: items `[loc(peer, medicine)]`, visits `[medicine: supply_match True]` (duplicate supply: confirmed, saved nothing). Result: 20 applied lies, credit oscillates 2 -> 1 -> 2; bound with n_saved = 0: 12.
* **CE-2 (label spreading).** Each mission one file with eight items: `loc(s, medicine)` and `loc(s, water)` for each s in {peer, memory, inventory, operator}; visits `[medicine False, water True]` whenever a reorder was applied. Result: 40 wasted visits in 40 missions (credit never throttles).
* **CE-3 (rate attack, bound not violated).** Each mission items `[loc(peer, medicine), loc(peer, water)]`, same visits. Result: 11 wasted visits in 40 missions = 2 + floor(38/4); bound 12; paper's remark predicts 8.
* **CE-4 (hazard unpriced).** Hard-refusal mission: a `hazard` item on station X; decision at X refused at tau_c only, `caution_refusals` absent -> `visits_from_mission` gives `(refused, refused_base) = (True, True)`; `settle` charge 0 every mission, any number of missions.
* **CE-5 (certified peer unreachable).** `new_ledger(certified_peers=('p1','p2'))`, items `hazard` with `peer_id` p1 and p2 through `plan_with_credit`: result 1 applied, 1 throttled, one account `peer`.

---

## 3. R6 critical points: status (one line each)

Section 2 of R6 (chain coherence)
* 2.1 Link 3 rhetorical: **partly** (Prop. 2 now stated with eps_any, abstract uses it; contribution (ii) still says look-around "makes eps small enough for such a bound to mean something"; k eps-hat is still vacuous at k=4).
* 2.2 Link 5 mixes scene text and realism: **partly** (the Realism paragraph now says "scene-distribution shift inside Gazebo"; the section title still joins them).
* 2.3 "dominated by hidden fires" is 3 events: **fixed** (text says all registered false approvals came from the correct-supply visible-fire images; count printed).
* 2.4 pending tags kept in Fig. 1: **fixed/ok until freeze** (tags present).
* 2.5 quotable contribution once, verbatim: **open** (abstract and contribution (i) still differ).
* 2.6 contributions (ii),(iii) not co-equal: **open** (three-item list unchanged).

Section 3.1 (Prop. 2)
* P1 frame independence / depot history: **fixed** (A1 stated; "without A1" supremum; stationary average flagged as non-bound).
* P2 eps_any instead of the sum: **fixed** (Prop. 2 is stated with eps_any; abstract uses it; but see "independent of k" in Sec. 1.1).
* P3 conditional epsilon: **fixed in S10** (class event C(w), Pr[U|C] <= Pr[E|C]); not in the main text.
* P4 world adversary / best-of-N: **partly** (A4 excludes it by assumption; no best-of-N search).
* P5 label circularity (perceivable by own views): **partly** (six-view label and oracle-steering in W/XD as secondary; the share of hard fires invisible in all of F/L/R is still not in the main text; "614-2000 px" vs Fig. 3a not reconciled).
* P6 notation Pr[unsafe | a]: **open** (A4 wording makes it worse, Sec. 1.1).
* P7 supply parse from the same operator text: **open** (the threat table lists only the destination parse).

Section 3.2 (cost bound)
* C1 delta is a simulation number: **partly** (abstract says "at the simulated false-alarm rate"; per-site delta not tabulated).
* C2 scrutiny not in bound: **fixed** (S term in (i), main "Price").
* C3 persistence / flooding: **partly, now with holes** (credit added; V1-V4 above).
* C4 soft refusal needs a duplicate: **fixed** (main "Price" says so for the arena).
* C5 independence in 1-(1-delta)^v: **fixed** (Boole 3k delta form first).

Section 3.3 (audit)
* A1 two audits: **fixed** ("What the evidence is").
* A2 reference implementation by the same authors: **open** (still "independent reference implementation"; wording and a third-party oracle both missing).
* A3 external timestamp of registrations: **open** (still a commit in the authors' repo; B registered the same day it was drafted; A/S/X/XD still DRAFT).
* A4 state audit power: **partly** ("five bugs, three more, all injected bugs killed"; no n/N injected-fault count).

Section 3.4 (trust base)
* T1 delivery interlock: **partly** (I-22 implemented, off by default, Gazebo check pending; TCB table still says "ROS wiring (reviewed)").
* T2 allow-list hash in TCB: **open**.
* T3 same-host assumption in the TCB table: **partly** (S10 text yes, table no).

Section 4 (pending designs)
* 4.1 A-steer power and wording, label rule, "self-filter", design-space demonstration: **fixed in wording and prereg draft 3**; the abstract still compares naive vs ours only and does not print ours vs control (exposure): **open**.
* 4.2 S: "closes" qualified, occlusion counted, D-safety a criterion, Table I updated to 64 worlds / six arms: **fixed**; detector-aware sign set: **declined explicitly** (honest, but a reviewer will still ask); main text still lists seven flip rates: **open**.
* 4.3 X: depot sentences rewritten to M0 vs M2 + steering descriptives; X-s descriptive; XD O1/O3/W-a1 restated so they can fail; tongues_small to 100; cause taxonomy fixed: **fixed**; XD-R recall is delegated to P2 (stated): **ok**.
* 4.4 V4 weak margin: **partly** (the margin is registered and explained; the main text should say "at most 3 more than M0", not "no safety cost"); Q in the paper: **fixed** (S12 row, one sentence, human spot-check pending).
* 4.5 abstract wording: **mostly fixed** ("in simulation", "only at image level on photographs", "at the simulated false-alarm rate", failed-claim count in last sentence).

Section 5 (presentation)
* Title "Relief Delivery Robot": **open**. Headline Pareto figure (unsafe vs time, real data): **open**. Table II resizebox: **open**. `\freeze`-style build failure on `\TBD`: **open** (numbers.tex still defines `\TBD` as grey text; 55 tokens). Study count 19 to 21: **fixed**. Fig. 5 move: **open**.

Section 6 top-8: #1 wording freeze **done**; #2 eps_any **done**; #3 labels **partly**; #4 assumptions **done**; #5 TCB/interlock **partly**; #6 overclaims **mostly**; #7 S defence **partly**; #8 credibility finishing **open**.

---

## 4. Do the claims outrun the evidence now?

* **The headline of the abstract (relative bound under any advice) is proved and is not run-dependent.** Good. Keep. Fix "independent of ... k".
* **"Machine-checked / audited" language.** The audit recomputes the same module; the new credit code adds a second *unaudited* layer whose bound the property test checks only in the form debit <= C + refund + shadow, which is true by construction. The test never compares against ground-truth savings, never uses duplicates, scrutiny misses, hazard charges from a decision, or source labels from a file. So "a property test drives the implementation ... and checks both bounds" is accurate but the bounds checked are the weak ones. A reviewer who reads advice_credit.py will find V1 and V2 in minutes.
* **Prop. 3 in the main text.** The main Limits sentence moved from "unbounded" to "bounded by a per-source credit ... (descriptive model, closed loop pending)". "Closed loop pending" is honest, but study B is a *mechanics* study with deterministic predictions (k=2, single copy, location only, one label), so it cannot confirm the bound in the cases where it fails. After B succeeds the sentence will read as stronger than the evidence.
* **Necessity.** Main text states the necessity without N (Sec. 1.2); this is a theory claim, not pending evidence, and it is the sentence most likely to be quoted back at the authors.
* **Pending studies (A, S, V, W, X, XD, Q, B): 55 `\TBD` tokens.** The prose is written as if results exist ("unsafe deliveries were TBD", "the registered headline claim ... is \HHeadline"). That is fine as scaffolding, but the *current* paper has no result for steering, the depot, scene text, the look-around replication or the model-prediction test; what it can already claim is G, H, T1/E, P/P2 and the proofs. The registration status is also uneven: V, W, B, IF registered; A, S, X, XD DRAFT; Q registered with a human spot-check pending. "Every study is registered before its first trial" is true of intent and of the merge plan, not yet of A/S/X/XD.
* **Descriptive model vs registered claim.** The credit model (Fig. credit) is labelled "descriptive, not registered" in the supplement; keep that label in the caption and in any main-text mention; do not quote its numbers (59 s, 295 s) beside registered numbers. Its adversary is weaker than the best known attack (V6).
* **Sim-to-real.** Unchanged since R6: everything closed-loop is Gazebo; real appearance is image-level only (P, P2, Q, XD-R). RA-L tolerates this if the abstract says it (it does); ICRA reviewers will still ask for a hardware or at least real-camera-on-robot result.
* **Registration as evidence.** B was drafted and registered within hours on 2026-10-18 by the author who also wrote the code under test; with an in-repo timestamp this is process hygiene, not independent evidence (R6 A3 still open).

---

## 5. Top-5 changes to raise acceptance probability (ranked)

1. **Land the pending studies in the dependency order and freeze (W, A with A-steer, XD, X, S, Q; B last or dropped from the critical path).** They carry every empirical claim after G and H; with 55 tokens pending the paper cannot be scored. B is a 1.3 GPU-hour mechanics check and a distraction on a 4-core host with a timing-sensitive run; run it only after the others, and only after the fixes below (otherwise it registers behaviour you are about to change). Effort: about 25-38 GPU-hours serial plus 1-2 days of analysis writing; the largest single factor (RA-L 40% -> 50-55% if they land as designed).
2. **Repair or shrink the credit theory (V1-V5) and restate Necessity.** Code: stamp `source` from the channel; drop the +1 refund (or refund only when the baseline order is known to have been wrong) and add time regeneration to the location pool; classify caution-only from `pre_caution_reason`; carry `peer_id` through `validate`; charge hazard-stop deliveries lost at an advised station; add CE-1..CE-5 as unit tests and extend B's honest cell with a duplicate-supply sequence. Text: Prop. 3 with n_conf and per-channel total, "at most one extra visit", Necessity as the decomposition of Sec. 1.2 with its premise. If time is short: delete the Limits sentence about credit from the main text and keep credit as a supplementary extension. Effort: 1 day (code 3 h, tests 2 h, text 2-3 h); removes the one place where a reader with the repo open finds a real counterexample (-5 to -8 points of risk, +3 to +5 if clean).
3. **Claim hygiene and one-line fixes before the freeze.** Abstract "of k" to "of the order and the advice"; quote the contribution sentence verbatim once in abstract/intro/conclusion; contribution (ii) rephrased (look-around reduces eps; the bound holds for any eps); "independent reference implementation" to "second implementation by the same authors from the same specification"; main Necessity sentence with its premise; A4 "does not influence (w, xi)"; main Limits credit sentence aligned with Prop. 3; V4 wording "at most 3 more than M0"; print ours-vs-control beside ours-vs-naive; add a `\freeze` switch that makes `\TBD` a `\PackageError`; title: "Relief Logistics Robot (in Simulation)" or drop "Delivery". Effort: 0.5 day; avoids the cheap rejections.
4. **Close the weakest TCB cell: switch the delivery interlock (I-22) on and check it in Gazebo for A-steer and X (or at least for the safety-critical cells), and list the allow-list hash and same-host assumption in the TCB table.** Moves "mission gating = reviewed" to a small component with the guard's property and makes A3 literally enforced instead of audited afterwards; this is the question a security reviewer asks first. Needs an amendment if A/X are already registered, so do it before they are. Effort: 1-1.5 days including the Gazebo check.
5. **Credibility package.** (i) External timestamp of every registration (signed tag mirrored to Zenodo/OSF, one hour); (ii) a person not involved writes the 60-line oracle from the one-paragraph rule and a 10% human spot-check of Q's labels (2-3 h); (iii) the missing headline figure (unsafe deliveries with Wilson bars against mission time for M0/M1/M2 and the advice arms, from real data) in place of Fig. 5; (iv) one real-camera result through the gate (a few dozen phone photos of real water/medicine packs on a shelf with a fire-free scene is enough for the supply check; or a mast-camera capture in a real room), to answer the "no hardware" objection at least at the sensor level. Effort: 1 day total; (i)+(ii) are cheap and remove standing objections, (iii)+(iv) raise ICRA more than RA-L.

---

## 6. Things that are good and should not be touched

* Prop. 2 with eps_any, the sharpness argument, the without-A1 supremum remark, and the "relative, not absolute" paragraph: unusually candid and the proof is short and right.
* Stating Necessity at all is the right instinct (it turns the rule into a design principle and separates the paper from filter defences); it needs the premise, not removal.
* The (sigma, rho) regulator framing and the honest "trade-off is unavoidable" remark; the literature note with verified references.
* Reporting failed registered claims; preregistration texts that say in advance what must not be claimed (A-steer power, S "closes", X depot sentence).
* The property-test habit (it found the scrutiny-reservation bug on its first run): extend it with the counterexamples above rather than replacing it.
