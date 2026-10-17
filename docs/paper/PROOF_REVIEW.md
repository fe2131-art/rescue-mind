# Proof review: Observation 1 / Proposition 2 / cost bound

Scope: `docs/paper/main.tex` (Sec. "Memory and other untrusted inputs as advice"), `docs/paper/supplement.tex` (Sec. S10), and the code
`rescuemind/{advice,stations,mission_memory,adaptive_views,caution_soft,delivery_interlock,delivery_permit}.py`, plus the places where they are
wired in (`ros/gazebo_waypoint_mission.py`, `rescuemind/local_vision.py`, `rescuemind/local_run_audit.py`, `scripts/local_vlm_server.py`).
Nothing was built or run. Line numbers refer to the worktree at the time of review.

## Verdict: sound with fixes

The core inclusion (unsafe delivery implies E_w, hence P <= eps_any <= sum eps_s) is correct and the proof step "stricter conjunctions imply weaker ones"
is valid. What is missing is (a) a precise probability space and one explicit independence/exogeneity assumption that the proof silently uses,
(b) a definition of "unsafe" that is contained in "must-refuse", (c) one wrong sentence about the depot ("or the stationary value"), and (d) a cost bound that
is loose in one place (reordering), under-counts in two (scrutiny, memory feedback) and uses a plug-in rate that goes the wrong way.
No gap found that makes the delivery-safety statement false for the arena; the depot statement is not valid as written.

## 1. Are the statements precisely defined? (gaps)

1. **Probability space is never written down.** The text says "over worlds and noise" but the proof needs the following, which is nowhere stated:
   * omega = (w, xi): w from the world generator (supply arrangement, fire, lighting, props), xi exogenous sensing/model noise.
   * **A1 (frame exogeneity).** The frame at (station s, pose p) is a function F(w, s, p, xi_{s,p}) that does not depend on the plan, the visiting order,
     the time of the visit or the history. The pointwise step "A_theta'(o_s)=1 implies A_theta(o_s)=1 *on the same frames*" is only meaningful under A1
     (potential-outcomes coupling). Under advice the robot captures *different realised* frames than the baseline robot would, so without A1 the
     implication says nothing about the law of o_s. The paper states A1 only as a caveat for the depot; it is the load-bearing assumption of the arena proof too
     (real Gazebo rendering and arrival-pose jitter are not exogenous to the route).
   * The VLM is a deterministic function of the image in the server (hazard answers are cached by image digest, `scripts/local_vlm_server.py:355-362`), so xi is rendering/pose noise.
2. **What the adversary controls and knows.** "Knows the world and the rule" is written as a(w). The proof actually covers the stronger, cleaner class a(w, xi)
   (clairvoyant: sees all frames), because the inclusion 1_U <= 1_E holds pointwise in omega. State that; it also makes "adaptive across missions" free
   (advice for mission t may depend on everything before), per mission. What is *not* covered: an adversary that influences w (moves supplies, lights a fire) or
   xi, and an adversary that changes the generator's law. The threat model says this ("cannot change the camera pixels") but Prop. 2 should list it as an assumption
   (A3: w independent of the advice).
3. **"Unsafe delivery" vs. "must-refuse".** main.tex Sec. Threat model: unsafe = "a wrong supply, or a delivery from a station with a fire". The error-budget paragraph defines
   M_s = wrong/no supply **or a *perceivable* fire (>= 614 px in one of three design views)**. The proof step "an unsafe delivery means M_s(w) holds" is only valid if every
   fire that the ground-truth audit counts as unsafe is perceivable. A fire below 614 px in all three views is "unsafe" but not "must-refuse"; then U is not a subset of E_w. Fix: either define
   unsafe := delivery from s with M_s(w) (and report non-perceivable fires separately as outside the guarantee), or state that the generator only creates perceivable fires.
4. **Mission-time vs. check-time world.** M_s(w) is evaluated at check time; the proof treats it as the state at delivery time. Needs "the world is static between check and delivery" (true in the arena, false in the depot, see 6).
5. **Per-mission vs. over missions.** "Pr_w[unsafe under a(w)]" is per mission. Over m missions with a persistent world and deterministic frames the event E_w is the same event every mission (so no accumulation);
   with fresh noise it accumulates at most as m*eps_any (union bound). Neither is said. The per-class numbers (eps-hat for "the hard class") are conditional on a class event C(w); the bound then reads P[U | C] <= P[E | C], which is valid, but say so.
6. **"eps_any does not depend on k".** Misleading. eps_any = P[exists s ...] depends on the site (and weakly increases with the station set); what is true is that the *bound* has no k-dependence beyond the union
   in E_w, and that it is independent of the order and the advice. Also eps_any >= eps_max, so "k*eps_max" is an upper bound only; say "does not depend on the order or on the advice".
7. **"Attained by an attacker ... when a clean duplicate supply exists."** Equality P[U]=eps_any needs a *clairvoyant* attacker (knows the realised frames, i.e. deterministic frames or xi observed) and a plan rule that lets
   him put any one station first. In the code that holds (see 4.f). A duplicate supply is needed for the **control** to have risk 0 (so that advice *increases* risk), not for equality with eps_any.
8. **Dangling "Corollary 1".** supplement.tex:317 cites "Corollary~1", but main.tex only says "the sum is a corollary" and the supplement has Lemma 1 and Proposition 2 only. Either number it or change the reference to "Prop.~2".
9. **Scope of "any advice".** The proposition holds for a *base* plan of mode off or verified. In `advice.py:199-239` (`assert_monotone`) the invariant is relative to the plan before advice, so a naive-memory base (`skip_check=True`) passes it.
   That is intended ("relative guarantee under a naive memory base", `advice.py:145-147`) but then Prop. 2 does not apply to that arm; the paper should say "base plan = baseline or verified memory". The interlock separately rejects any plan with `skip_check`/`deny_without_visit` (`delivery_interlock.py:105`).
10. **The depot sentence is wrong.** main.tex: "There eps must be read as a supremum over predecessors, arrival-pose laws and visit times, **or as the stationary value that we measure**." A stationary average is *not* a valid replacement: the attacker chooses the order, hence the predecessor,
    hence the arrival-pose law, so he can select the worst arrival history; only the supremum (or an explicit bound over the reachable histories) keeps the proof valid. Delete the "or ..." clause, or call the stationary value an *estimate of a lower bound* of the supremum. The same holds for
    smoke-emitter phase: detours change visit times.
11. **Image-level estimate of eps_s.** "can be estimated directly from images of every station of every world" holds only if the images are drawn from the closed-loop frame law (arrival poses, aiming error). T1/XD images are design-pose renders; the paper's own T2/F results show that image-level and closed-loop rates differ. Say "at the design poses".

## 2. Is each proof step valid? Hidden assumptions

* **Obs. 1 / Lemma 1.** Valid as a statement about the predicate. The plan has no field for tau_s and V is only enlarged (scrutiny), so equality for tau_s is by construction. Direction of the hazard conjunct: approval iff p < tau, so a lower tau is stricter; code refuses at p >= tau (`mission_memory.py:47-49`), consistent. Rounding: `hazard_prob` is rounded to 4 decimals by the server (`local_vlm_server.py:330`); a raw p >= 0.01 always rounds to >= 0.01, so rounding can only make the caution *stricter*. OK.
* **"theta' = (tau_s, min(tau_h, 0.01), V)" is not literally what the code does.** The code never computes a min: the caution is an *extra conjunct* [max(p1,p2) < 0.01] on top of the server's own label `scene != 'hazard'` (`mission_memory.py:46-49`). The conjunction equals [p < min(tau_h, 0.01)], so the formal statement is right, but only because the server's threshold is a conjunct, not a parameter that the client knows (see 4.a).
* **A_theta in the paper is not what the client recomputes.** Eq. (rule) says p_h < tau_h with tau_h = 0.05. The client (`local_vision.local_decision`, line 117; `local_run_audit` line 29-32) reads only the **label** `scene`; tau_h lives in the server flag `--hazard-threshold` (default **0.5**, `local_vlm_server.py:206,504`; campaigns pass 0.05). Neither `validate_result` nor the audit checks that the recorded `hazard_threshold` equals 0.05. The theorem is about the rule as written; the code enforces the rule for whatever threshold the server was started with. This is a trust-base item, not a flaw of the proof, but the trust table should list "server threshold = 0.05 (not audited)".
* **Delivery needs A_theta' at the delivering station.** This is the other load-bearing premise and it is a property of the mission node, not of `advice.plan`. The proof in S10 argues it ("a refusal without a visit is not a plan option") but it holds only if every path to the delivery leg (first station, recovery hops, soft refusal, k-station search) passes through an approval of the *current* station. I checked: `ros/gazebo_waypoint_mission.py:788-818` (search starts only on refusal, `next_candidate` excludes checked stations, `stations.next_candidate`, `validate_visits`), `caution_soft.audit_caution_refusals` (refused station never delivered from, no repeat). That is consistent, but it is verified by audit after the run, and by the permit only when I-22 is on (off by default). The paper says this correctly in "What the evidence is"; keep it as an explicit assumption A4 in the proposition.
* **Extra views (I-20, scrutiny) only add refusals.** True for the *predicate*: extra poses are tested with the same caution tau (`look_around_peek` -> `onsite_check(peek=True)` -> `peek_hazard`, `mission_memory.py:52-57`) and any hazard flag turns the approval into a refusal (`local_vision.combine_with_look_around`). Hidden assumption: the extra views are *taken after* the front/L/R frames, so they do not change those frames (A1). If scrutiny is on and `--look-around` is 0, `schedule_adaptive_views` is never reached (it is called only from `look_around_peek`, gazebo_waypoint_mission.py, `look_around_peek`), so no extra views are taken; `audit_scrutiny` then raises (advice.py `audit_scrutiny`, "approved without the extra views"), i.e. the run is flagged, not silently weakened. Fine, but document that scrutiny requires look-around.
* **Soft refusal never delivers from a suspicious station.** True and audited (`caution_soft.py:audit_caution_refusals`; `delivery from a caution-refused station` raises). Two precision problems in the prose: (i) "a real hazard (p >= tau_h) still stops the mission" is true only for views *already taken*. `look_around_peek` returns `SOFT_PEEK` at the first caution-only side view (gazebo_waypoint_mission.py:636-644) and the other side view of that station is never looked at, so a real hazard in the unseen view neither stops the mission nor is recorded. Safe for delivery (that station is never delivered from) but the sentence over-claims. (ii) The soft refusal changes the route: a mission that the baseline would have stopped (hazard seen later at that station) now continues to another station. That is covered by eps_any (union over all stations), not by the single-station argument; say so.
* **Union bound.** Valid without independence. Note the sum counts every station although a mission with the supply at the first station never checks the second; it is an upper bound, not tight.
* **Scrutiny does not improve the bound.** Scrutiny lowers the risk of the *steered* station only (`advice.py:148-157`: caution + extra views at the station that location advice moved to the front). After a wrong-supply refusal at that station the search proceeds to unscrutinised stations, so the worst case is still eps_any. A rigorous statement of the benefit needs the second-order quantity eps_s^scr = P[M_s and A_scr(o_s)], and "P[U] <= max over j of ..." does not simplify. Keep scrutiny as an empirical claim (A-steer), not as part of Prop. 2.
* **Monotone invariant vs. formal rule (`assert_monotone`, advice.py:199-238).** It is a check on the *plan*, not on theta': it compares caution/skip/deny/scrutiny/order between `before` and `after`. It does **not** check tau_s or V (they are not in the plan) and compares the new caution only against the old caution, not against the baseline tau_h; it requires 0 < tau < 0.05 with the constant `V36_TAU_H = 0.05` (advice.py:31), also hard-coded in `local_run_audit.py:29`. Consequences: (a) the audit is conservative if a site uses a different baseline threshold (K conformal, P2 calibrated 0.3, server default 0.5), where a caution of 0.01 is still stricter but a caution of, say, 0.06 would be rejected although it would also be stricter than 0.5; (b) conversely it would accept a caution that is *looser* than the baseline if the baseline tau_h were below 0.01, but then the caution is a no-op conjunct, so Prop. 2 still holds. Neither breaks the proposition; both mean "the invariant as enforced" = "the plan only adds caution/reorders" which is *sufficient* for the formal rule, not equivalent.
* **k-station order.** `assert_monotone` requires the order to be a permutation of the plan before advice only when an `order` key exists (k > 2, `advice.py:225-229`). In the two-station arena the plan has no `order`; the search order is rebuilt in the mission node as `[head, other]` (`gazebo_waypoint_mission.py:530`, `search_context`). So "advice cannot drop a candidate" is enforced by construction (arena) and by assertion (depot). `stations.validate_visits` checks, in the run audit, that visits are a prefix of the order (`recovery_evidence.py:49-51`). Consistent.
* **"A location item moves j first; all other items leave pi unchanged"** (supplement) is slightly different from the code: only the **first** applicable location item is applied; later ones are rejected as "already proposed" because the condition `out['first_station'] == cat and st != cat` (advice.py:146) fails after the first reorder; an item naming the catalog station is also rejected; and if the base (memory) plan already reordered, advice reorder is rejected. This does not matter for safety but matters for the cost bound (see 3.a).

## 3. Is the cost bound correct?

1. **(i) Reordering: k-1 is loose and measured against the wrong reference.** Code applies at most one reorder (above). Relative to the no-advice order (the robot's own default), the extra work is at most **one** extra station check: if the advised station has index i and the true one j in the default order, the true station's position is j+1 if i > j and j if i < j. "k-1 wasted visits" is the bound relative to the *oracle* order. The paper's "3W in the depot" is therefore 1W for the extra-cost relation to the control, and (k-1)W only for regret relative to the oracle. State which.
2. **A hazard stop is not a bounded time cost.** If the advised first station really burns, the mission ends without delivery although the baseline would have delivered from the clean station. That is a lost delivery (an availability event with probability P[advised station perceivably burns]), not "at most W".
3. **(ii) the plug-in numbers are not upper bounds.**
   * delta = 4/193 was measured at tau = 0.0113, not at 0.01 (supplement:421, "an approximation"). The false-alarm rate is non-increasing in tau, so delta(0.01) >= delta(0.0113): the approximation goes the wrong way. Measure at 0.01 (it is a post-hoc threshold on saved scores, no new inference needed) or state that it is an underestimate.
   * It is a point estimate with a Wilson 95% interval of [0.8%, 5.2%]; a *bound* should use the upper limit: v = 3: 0.149 (indep.) / 0.156 (Boole); v = 6: 0.274 / 0.312, versus the printed 0.061 and 0.118.
   * 1-(1-delta)^v is an upper bound on P[at least one alarm] only if the per-view alarms are (positively) associated, which is plausible (same scene, same look-alike object) but is an assumption; the assumption-free bound is v*delta (the paper gives both, but calls the first one "at most").
   * delta was measured on held-out fire-free *images*, not on the three closed-loop views of one station; the views of one station are strongly correlated, which makes the union over views *smaller* than independent, fine for an upper bound, but then P[false refusal] is closer to delta than to v*delta and the per-station rate is the quantity to measure (cluster by station/world).
   * The "worst case v = 3k = 6" counts views that are never taken: in the arena the second station is visited only after a wrong-supply refusal at the first. A valid, tighter bound is per visited station.
4. **Omitted cost: scrutiny.** Scrutiny gives the advised station the caution threshold and three extra poses (0.8 m offsets and 0.3 m near) on **every** location-advised mission, including truthful ones (code: advice.py:148-157, gazebo_waypoint_mission.py:510-526). It adds a time term S (three drives + settle + two inference passes each) and raises the view count at that station to 6 (front, L, R, L2, R2, N), so the false-refusal term is 6*delta-bar (0.12 point estimate, 0.27 with the upper limit). Neither is in (i)-(iii).
5. **Omitted cost: memory feedback.** `observations()` records a hazard whenever a view is flagged **under the caution threshold** (`mission_memory.py:74-79` `_front_hazard` uses `memory_caution_tau_h`; peeks use `peek_hazard(..., tau)`). The memory plan then keeps caution for the last HORIZON=3 missions (`mission_memory.py:161-175`). A fire-free station whose views sit at p in [0.01, 0.05) is refused under caution, which writes a hazard record, which renews the caution: **a single caution-level alarm can pin the station in caution forever**, and since frames are near-deterministic the false refusal repeats every mission. This is not "persistent peer advice" (the paper's only multi-mission caveat) but the robot's own record, and the per-mission bound does not cover it. Either record the hazard only when the *standard* rule flags it (use base reason, not the caution tau) or state the cost as unbounded in the number of missions.
6. **Soft refusal does not remove the one-shot kill in general.** (iii) says caution-only refusal "removes the one-shot mission kill". It saves the delivery only if a *further candidate holds the requested supply*. In the 2-station arena the supply is at one station, so a soft refusal of that station still ends without delivery (the other station refuses for wrong supply). The benefit is conditional on a duplicate supply (depot). Cost of a soft refusal is one wasted visit including side views (more than W as defined, because W = drive + front check, and the soft-refused station already passed the front check and had look-around views).
7. **Definition of W.** W is the median extra time of the *control* when the supply is at the other station (supplement, S10). The reordering case in the same configuration (advice wrong) is the same quantity only when look-around is on in both arms; check that W is taken from arms with the same flags (look-around/adaptive on).
8. **Numbers re-checked.** 1-(1-4/193)^3 = 0.061, ^4 = 0.080, ^6 = 0.118; 6*4/193 = 0.124. Printed values are correct.

## 4. Gaps between the math and the code (file:line)

a. `rescuemind/local_vision.py:117` and `rescuemind/local_run_audit.py:29-32,61`: the hazard conjunct is the server's label; tau_h = 0.05 is not checked anywhere on the client (server default 0.5, `scripts/local_vlm_server.py:206,504`). `validate_result` (local_vision.py:51-63) does not touch `scores`.
b. `rescuemind/mission_memory.py:29-34` vs `rescuemind/adaptive_views.py:12-16`: the same score is parsed fail-open in one and fail-closed in the other. `_hazard_prob` returns **0.0** on TypeError/ValueError (a malformed or string `hazard_prob` disables the caution), `adaptive_views._p` returns **1.0**. Missing `scores` gives 0.0 in both (`or 0.0`). The caution is an extra conjunct, so Prop. 2 is unaffected (no caution = the baseline), but the "caution applied" claim and the audit (which recomputes with the same function from the same saved outputs) are self-consistent only; make `_hazard_prob` return 1.0 on error, as the NaN branch already does, and have `validate_result` require a finite `hazard_prob` in [0,1] when caution is used.
c. `rescuemind/mission_memory.py:74-79,85-96` + `:155-163`: caution-level alarms are recorded as hazards (3.5).
d. `rescuemind/advice.py:146`: location advice is silently dropped when memory already proposed a reorder or when it names the catalog station; the supplement's description of the planner ("a location item for station j moves j first") should say "the first applicable one".
e. `rescuemind/advice.py:31,236` and `local_run_audit.py:29`: the 0.05 constant duplicates the threshold of one rule version; for P2/K-calibrated sites the audit and the plan reject legitimate cautions (conservative).
f. Attainment (Prop. 2 "attained by"): the plan rule allows the attacker to place any non-catalog station first (advice.py:146-151) and nothing else about the order; with duplicates the control checks the catalog station first. So the steering part of the attack is faithfully modelled by the code; the unmodelled part is knowing the realised frames.
g. `ros/gazebo_waypoint_mission.py:636-644`: soft peek returns before the second side view (3, soft refusal).
h. `rescuemind/delivery_interlock.py` recomputes from *saved model outputs*, not by re-running the model; it checks image hashes, plan monotonicity, that the station's caution was applied (`memory_caution_tau_h <= tau_plan`) and, only if configured, that L/R/adaptive views were taken (`need_la`, `need_ad` come from the policy or from the record's own config, i.e. a record that claims `look_around: 0` is not required to contain side views unless the interlock policy says so; lines 142-148). For a guarantee that includes V it should be launched with `require_look_around=True` (and adaptive when scrutiny is on). `delivery_permit.py` itself is sound as a gate (hash-bound, TTL, optional HMAC, fail closed, geofence uses the guard's own odometry); without a key it protects against bugs only (stated).
i. Dependence on the unaudited server: `Policy.image_root`/hashes establish that the saved images are the ones the saved outputs refer to, not that the outputs came from the model (`scope: SELF_REPORTED_LOCAL_TRANSFORMERS_NOT_GPU_ATTESTATION`, `local_run_audit.py:67`). Already in the trust table ("VLM outputs as recorded").

## 5. Minimal rigorous restatement

### Proposition 2 (advice stays inside the error budget), one column

```latex
\textbf{Setting and assumptions.}
A site has $k$ stations. A sample point is $\omega=(w,\xi)$: a world $w$ from the generator and exogenous noise $\xi$.
For a station $s$ and a pose $p$ from the finite design set $\mathcal P$ (front, $L$, $R$, and the three extra poses) the
frame is $o_{s,p}=F(w,s,p,\xi_{s,p})$. For $\theta=(\taus,\tauh,V)$ with $V\subseteq\mathcal P$,
$A_\theta(o_s)=C(o_{s,\mathrm{front}};\taus,\tauh)\wedge\bigwedge_{v\in V}[\,p_h(o_{s,v})<\tauh\,]$.
$M_s(w)$: station $s$ holds the wrong or no supply, or a perceivable fire; \emph{unsafe} means a delivery from some $s$ with $M_s(w)$.
\begin{itemize}\itemsep0pt
\item[A1] \emph{Frames are exogenous:} $o_{s,p}$ does not depend on the plan, the order, the visit time or the history.
\item[A2] \emph{The plan only tightens:} for every advice set $\mathbf a$ the plan gives each station $s$ parameters $\theta'_s=(\taus,\tauh',V')$
          with $\tauh'\le\tauh$, $V'\supseteq V$ (Lemma~1, audited by \texttt{assert\_monotone}), and the base plan is the baseline or verified memory.
\item[A3] \emph{Gate:} the robot delivers from $s$ only if $A_{\theta'_s}(o_s)=1$ on the frames it captured at $s$ (mission node; I-22 if on).
\item[A4] $w$ is independent of the advice; the adversary may be any function of $\omega$ (clairvoyant), adaptive across missions,
          but cannot change $w$, $\xi$, the model, the code or the guard.
\end{itemize}
\textbf{Claim.} Let $E=\bigcup_{s\le k}\{M_s(w)\wedge A_\theta(o_s)=1\}$, $\varepsilon_s=\Pr[M_s\wedge A_\theta(o_s)=1]$ and
$\varepsilon_{\mathrm{any}}=\Pr[E]$. Then for every mission and every advice map,
\[\Pr[\text{unsafe}]\;\le\;\varepsilon_{\mathrm{any}}\;\le\;\min\Bigl(1,\sum_{s=1}^{k}\varepsilon_s\Bigr),\qquad \varepsilon_{\mathrm{any}}\ge\max_s\varepsilon_s,\]
and over $m$ missions $\Pr[\exists\,\text{unsafe}]\le\min(1,m\,\varepsilon_{\mathrm{any}})$ (equal to $\varepsilon_{\mathrm{any}}$ if frames repeat).
\emph{Proof.} Fix $\omega$ and an advice set. If the robot delivers from $s$ and $M_s(w)$, then $A_{\theta'_s}(o_s)=1$ by A3. By A2 the
supply conjunct is unchanged, $V\subseteq V'$ and $p_h<\tauh'\Rightarrow p_h<\tauh$, so $A_\theta(o_s)=1$ on the same frames (A1). Hence
$\omega\in E$. The inclusion holds for every $\omega$, whatever the advice depends on (A4), so take probabilities; Boole gives the sum. $\square$
\emph{Sharpness.} If the adversary may name any non-default station first and knows $\omega$, taking $j^*(\omega)\in\arg\{s:M_s\wedge A_\theta(o_s)=1\}$ makes the first check at $j^*$ approve,
so the bound is attained. \emph{Without A1} (depot: arrival pose and smoke phase depend on the history $h$) replace $A_\theta(o_s)$ in $E$ by $\exists h\in H_s:A_\theta(o^h_s)$ over the reachable histories; an average over histories is not a bound.
```

### Cost bound, one column

```latex
\textbf{Cost of wrong or hostile advice (per mission, against the no-advice robot with the same inventory order).}
Let $W$ be the time of one extra station visit (drive plus front check), $S$ the time of the three scrutiny views,
$\bar\delta$ an upper confidence limit (here Wilson 95\%) of the per-view false-alarm rate of $p_h\ge\tau_c$ on fire-free views, \emph{measured at $\tau_c=0.01$}, and
$n_s$ the number of views actually taken at station $s$ (3 under look-around, 6 under scrutiny).
(a) \emph{Reordering.} The plan applies at most one location item, so the number of extra checks is $\le 1$ (vs.\ the oracle order $\le k-1$); the time added is $\le W$
(plus $S$ with scrutiny, even if the advice is right). If the advised station really burns, the mission ends without delivery.
(b) \emph{Caution.} A fire-free station that is checked under $\tau_c$ is falsely refused with probability $\le n_s\bar\delta$
(Boole; $\le 1-(1-\bar\delta)^{n_s}$ if the views' alarms are positively associated), and only stations that are visited count.
(c) \emph{Price of a refusal.} Hard: the delivery is lost. Soft: $\le W'$ (drive, front check and side views of the refused station) and the delivery is lost only if no further candidate holds the supply.
Hence $\mathbb E[\Delta t]\le W\,[\text{loc}]+S\,[\text{scr}]+\sum_{s\ \mathrm{visited}}n_s\bar\delta\,\cdot\,\bigl(W'\text{ (soft) or } \ell\text{ (hard)}\bigr)$, where $\ell$ is the value of a lost delivery.
These bounds are for one mission; memory feedback (record of caution-level alarms) is not covered unless hazards are recorded only when the standard rule flags them.
```

## 6. Minimal list of edits (not done here; main.tex/supplement.tex are being copy-edited)

1. Add the probability space, A1-A4 and "unsafe := delivery from a must-refuse station" to Prop. 2 and S10; say clairvoyant adversary, per mission, m-mission union.
2. Delete "or as the stationary value that we measure" (main.tex Assumption paragraph, and the same sentence in S10 "error budget"); call it an estimate, not a bound.
3. Replace "$\varepsilon_{\mathrm{any}}$ does not depend on $k$" by "does not depend on the order or on the advice"; state that equality needs a clairvoyant attacker, not a duplicate supply.
4. Fix "Corollary~1" (supplement.tex:317) or number the corollary.
5. Cost bound: reordering <= 1 extra visit (k-1 vs oracle), add the scrutiny time and view count 6, use delta measured at 0.01 with the upper confidence limit, drop the unvisited-station worst case, say that a hazard stop is a lost delivery, and that soft refusal needs a duplicate supply.
6. Code: make `mission_memory._hazard_prob` fail closed (line 32), record hazards in memory from the standard rule only (`_front_hazard`, `peek` flags), pin/audit the server hazard threshold, start the interlock with `require_look_around` when the claim includes V.
