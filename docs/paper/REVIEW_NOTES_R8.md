# Simulated reviewer report, round 8 (after studies V and W, I-20 adoption, I-22 check, I-23 `make verify`, I-24 v2): `docs/paper/main.tex`, `supplement.tex`, `numbers.tex` on `i21-depot` (6ce75f1 / caebcb7)

Stance: hostile but fair, RA-L / ICRA program committee, robotics + security. Read-only: no LaTeX build, no Docker/Gazebo/GPU, no test suite (study A is starting on the host).
Sources read: `main.tex` (all), `supplement.tex` (S10 credit/necessity/trust base, Table S12, the W and V parts), `sec_formal.tex`, `numbers.tex` (all macros), `experiments/results/{v,w,g}_summary.json`, `PREREGISTRATION_{A,V,W}.md` (and the registration lines of S, X, XD, IF, B, Q), `docs/IMPROVEMENT_LOG.md` (I-22), `docs/FINDINGS.md` #29, `i22_gazebo_check.log`, `README.md` (generated part), `REVIEW_NOTES_R6/R7.md`.
Could not extract the text of `main.pdf` (no `pdftotext` on the host); the PDF is 10 pages according to `main.log`, built after the last `main.tex` edit. Macros were compared with the JSON for W, V and G only (all matched); H, T1, E, K, P were not re-derived.

---

## 0. Verdict (Japanese, short)

**判定: 論文の鎖 (ゲート → ε → 見回し → 助言は締めるだけ → 保証の外) は R7 から強くなった。W は「ε は十分小さいか」にほぼ答え、V は失敗を正直に書いている。残る穴は主張の細部と、A/XD/X/S がまだ無いことの 2 種類。**

* **W は鎖の第 3 リンクを実データで支えた**: 見回しの取りこぼし 3/150 (Wilson 上限 5.7% < 登録した 15%)、前方のみ 76/150、双子 75 件で余計な停止 0。ただし (i) 150 件は「ステーションの真後ろ ±0.15 m」という、見回しの設計と同じ幾何の家族で、側方視点からは構造的に見える。(ii) 一番効いている部分集合 (前方に出ない火 23 件) の取りこぼしは 3/23 = 13% (Wilson [4.5, 32]%) で、5.7% は 85% を占める前方可視の火で薄まった値。(iii) ε_any(2)=4.0%, ε_any(4)=7.8% は独立抽出の計算値で、k=4 の上限は 21% (登録の 15% を超える)。「小さい」は「前方のみ (76%/94%) より桁違いに小さい」としては支持、「安全論拠として十分小さい」としては未支持。
* **V は誠実だが、書き方に 3 つ穴**: (a) 抄録と結論が H の数字 (M2 0/32) だけを出し、V (M2 1/50, 記憶の安全の主張は不成立) を出していない。H+V をまとめると M0 1/82、M2 1/82、M1 40/82。(b) V4 の系列単位 McNemar は M2 が 1 件も危険配達を出さない限り通らない設計 (最小 p は 6 対 0 の 0.031。モデルの予測中央値は M2 で 1 件) で、「不成立」は検出力の問題。本文はそれを言っていない。(c) 絶対時間の予測は M0・M2 とも区間の外 (実測が 6〜8 秒長い) なのに、本文は「モデルの主張は支持」とだけ書く (差の予測が当たったのは事実)。
* **I-20 を既定にした判断**は、ルールが事前固定で、締める方向だけなので Prop. 2 を壊さない点では防御できる。ただし「利益の証拠」は 1 対 0 (p=1.0)、トリガーが働いた火の世界は 1/150。しかも v3.7 を閉ループで測った研究は 1 つも無い (A は v3.6)。**「v3.6 を測った、v3.7 は締めるだけの追加で効果の証拠は 1 世界」と書き、XD の適応腕で再確認し、基準を割ったら戻す、と事前に書くべき。**
* **古い記述が残っている (すぐ直せる)**: 本文 L159 と補遺 S10 の信頼基盤と README が「I-22 の Gazebo 確認は未了」と書いているが、実際は 10/18 に通過 (4 ミッション)。Discussion の失敗リストは 4 件のまま (\Nfailed は 6)。「ε の主因は前方から隠れた火」は W の内訳 (前方のみの取りこぼし 76 件のうち 54 件は前方で 614 px 以上見える) と合わない。「プロンプトより動く」は W 自身の参照行 (v3.5 の語句では見回しでも 48/150) と矛盾。
* **今すぐ必要**: study A の事前登録ファイルは先頭が「DRAFT for review」のまま。A の本番が始まる前に、状態行を REGISTERED + コミットハッシュに直し (B と IF は既にそうなっている)、外部タイムスタンプ (OpenTimestamps、HANDOFF で回答待ち) を取る。長さは 10 ページ (参考文献込み) で、RA-L/ICRA の上限 (8 ページ前後、要確認) を超えている。A/XD/X の数字が入ると増える。
* **採択確率 (主観)**: 現状 (A/S/X/XD/Q/B/IF が未実行、本文の `\TBD` が 19 箇所) で **RA-L 約 45%、ICRA 約 30%**。R7 の 40% / 28% から、W の ε 上限と V の誠実な報告、信用理論の修復で上がった。A・S・XD・X が設計どおり出れば **RA-L 約 58%、ICRA 約 40%**。特に XD の難しい火の上限が 15% 以下で出るかが ε の主張の分かれ目 (私の見立てでは 60% 程度)。XD がそれを割ると、「ε は小さい」はアリーナ限定に縮み、RA-L 50% 前後に落ちる。

---

## 1. How V and W change the story

### 1.1 W (look-around at image level, prior art)

**What W adds.** The registered claim is met (miss 3/150 = 2.0%, Wilson [0.7, 5.7]%, below 15%; 0/75 extra false stops; 75/75 twins approved; front-only 76/150; 0 inference errors; no fire hidden from all six views, 0/150, upper 2.5%). The failed part, W-b (hazard rule beats the vote and conformal baselines on the same inputs, 0 of 3), is reported as failed in the abstract count, in the main text and in Supp. S12, with the correct reading (the separation comes from wording plus crops, not the rule; the deployed check beats the vote at Holm p=0.023; conformal 0.05 buys 1 false approval for 74 lost correct approvals). That is honest and it does not hurt the chain: the chain never claimed the scoring rule as the contribution. It does remove a possible related-work claim against VAP-TAMP; the Related Work sentence "ours differs in closed-set next-token scores, ..." is a description of difference, not of superiority, and should stay so (add "W-b: not separable from a five-paraphrase vote at the same input").

**Is "ε small enough" supported now?** Partly. What the data support, and what they do not:

1. *Supported:* on a family of 150 new small, partly hidden fires, the look-around check misses 2.0% (upper 5.7%) against 50.7% front-only. The effect is not marginal, and G (1/16 vs 11/16) agrees. Closed loop agrees too: pooled over H and V the unsafe deliveries of the verified-memory arm and of the no-memory arm are 1/82 each (about 1.2%, Wilson [0.2, 6.6]%), consistent with ε of 2%.
2. *Not supported (scope of the number).* (a) **The family is the one the defence was designed for.** Fires stand "straight behind the requested station, 0.55-0.75 m back, lateral +-0.15 m" (`PREREGISTRATION_W.md` line 21); the side poses at +-0.4 m see behind the station by construction. The prereg expected n of about 130 perceivable worlds and got 150 of 150: perceivability is a property of the geometry, not a finding. "No fire hidden from all six views (0/150)" therefore measures the generator, not the world. The paper does say "one generator, the fire stylised; v3.6's wording was developed on the same generator", but the sentence "so a fire no view shows is excluded by the label and not estimated" should come with the geometry: *behind the station only; lateral, low, in front of the supply and behind another prop are not sampled*. (b) **The 5.7% is a mixture.** Of the 150, 127 are front-perceivable and 23 side-only. Look-around misses 0/127 and **3/23 = 13% (Wilson [4.5, 32.1]%)** (`w_summary.json`, `miss_look_around_side_only`). Side-only is exactly the class that the chain's link 2 calls the dominant source of ε (fires hidden from the front); the headline 2.0% is diluted by the easy class. Print both subclass numbers in the main text. (c) **ε_any(k) is a calculation under independence.** 4.0% (k=2) and 7.8% (k=4) are 1-(1-ε)^k on distinct random worlds, with upper limits 11.1% and 21.0%; at k=4 the upper limit exceeds the registered 15% line. The registration set the 15% line on one station; the paper's chosen reading ("tightly bounded") is true of that line only. A depot shares lighting and arrival pose between stations (the supplement says so), so the independence is the favourable case. (d) **Absolute smallness.** 7.8% at k=4 means an attacker who can name the first station can raise the chance of an unsafe delivery from 2.0% (catalog station) to 7.8% on the hard class; "relative, not absolute" is in the text, so this is fine, but the abstract's "small enough for such a bound to mean something" idea should not return: *small* is relative to front-only, not to a safety case. (e) **Image level.** Poses carry a modelled arrival error (spread measured on 132 runs). Study V's one M2 event (right view p_h 0.33 for M0, 0.013 for M2 in the same world, after arrival jitter, FINDINGS #29) shows that the score can move by a factor of 25 within that spread. W's jitter is drawn, so it is covered in principle; the closed-loop rate at the depot (X) is the test. Say so in one sentence.
3. *Chain link 2 vs the W breakdown.* Link 2 ("ε is dominated by fires hidden from the front view") reads as if the front view shows nothing. In W, 54 of the 76 front-only misses are front-perceivable fires (>= 614 px in the front view, front-only miss 54/127 = 43%); only 22 are side-only. What is true: the fires are small and partly hidden behind the supply, so the front check misses many fires that some pixels show; the side view shows 4 600-22 000 px. Reword link 2 and the Fig. 1 box to "small, partly hidden fires".
4. *"Moving beats thinking harder" (Discussion) is contradicted by W's own reference row.* Same worlds, v3.5 wording without crops: front-only 144/150, look-around 48/150 (upper 39.8%); v3.6 wording with crops: look-around 3/150. Moving removes 96 misses, the wording and crops remove 45 more (94% of what is left); the Supp. says "the v3.6 wording and crops are needed as well". T2 and F said the wording did not fix the *held-out/closed-loop* problem, but W says it fixes the residual after looking around. Replace "not from a better prompt" by "the largest single gain came from moving; after it, wording and crops removed most of what remained".

**Effect on the chain.** Link 3 is now the best-supported link of the paper. Link 4's guarantee does not depend on W at all; W makes its *budget* readable. The chain gets weaker at one point only: link 5/XD (does the budget survive clutter?).

### 1.2 V (repeated-mission model in closed loop)

* **Model claim supported** (V1-V3: saving 14.9 s inside the registered 11.3-20.1 s; unsafe counts inside their intervals, searches within +-3; Wilcoxon exact p=0.006, median per-sequence saving 17.6 s). Two things the paper does not say: (i) the *absolute* mean times of M0 (87.6 s vs [79.3, 86.2]) and M2 (72.7 vs [63.5, 70.5]) fall outside their intervals (`secondary_time_inside`: M0 false, M1 true, M2 false); only the difference is inside. The model underestimates mission time by about 6-8 s. "The model claim is supported" is correct for the registered V1/V2, but a reviewer reading the JSON will find the secondary line; add one clause. (ii) V1 as registered tests the *difference*, which cancels the common offset, so this is a weaker test than the sentence "the repeated-mission model predicts the closed-loop behaviour" suggests.
* **Memory claim not supported: honest, but with the reason missing.** The text says the margin held (M2-M0 = 1 <= 3) and the sequence test did not (6 sequences with M1 unsafe, 1 with M2, exact McNemar 5:0, p=0.0625). It does not say that, with 10 sequences, the smallest two-sided exact p with 5 discordant sequences *is* 0.0625, and that the test could only pass if M2 had no unsafe delivery in any of M1's six sequences, while the registered model predicted a median of 1 (0-5) unsafe deliveries for M2. So the test had a prior failure probability above one half; the failure is a power failure, not evidence of a safety cost. Say it in one sentence (the prereg amendment 3 already acknowledges the "one expected event" problem).
* **Diagnosis of the M2 event** (check error from arrival jitter, M2 plan had no caution): plausible and documented (FINDINGS #29, run ids), but it is the authors' post-hoc reading of one run; keep the wording "the I-20 trigger would have taken extra views" (what the 0.013 > 0.005 comparison shows), not "would have caught it" (the commit message's wording; the paper's is fine).
* **It is also a closed-loop instance of A1 failing.** Same world, same check, different arrival jitter, 25x different score: A1 ("frames do not depend on the plan, order, visit time, history") holds in the arena only on average. The supplement says A1 "holds in the arena with a fixed arrival pose ... only approximately"; Prop. 2's bound is on the law over omega = (w, xi), where arrival jitter is part of xi *if it is independent of the plan*; the V event shows it is not (M0 and M2 take different paths). Whether a clairvoyant advisor can choose a path that yields a favourable jitter is the same sup-over-histories issue the paper confines to the depot ("Without A1"). Move one sentence of it to the arena paragraph in the main text and cite V's event as the example; it turns a weakness into evidence of candour.
* **Abstract/headline selection.** The abstract quotes H only (M0 1/32, M2 0/32, M1 20/32). The Methodology says "the headline claims are G, H, V and A", and the Conclusion says "(H: supported)". V is a headline claim whose memory half failed and whose unsafe count points the other way (M2 1/50 vs M0 0/50). Either drop V from the headline list or report H and V together: "unsafe deliveries over 82 missions: M0 1, M2 1, naive memory 40". This is the cheapest credibility gain of the round (Sec. 4, #3).
* **Effect on the chain.** The failure does not weaken link 4 (the guarantee is a statement about E, and the one unsafe M2 delivery is in E by the paper's own diagnosis). It weakens the *speed-without-safety-cost* sentence, which is reported as "supported in H, not supported in V". Nfailed = 6 counts it, correctly.

### 1.3 I-20 adoption on one world

Defensible as an engineering decision, not as a result. For: the rule (`tau_sus` = 0.005) was fixed on development data before W was scored (Amendment 1), the adoption rule was committed before the scores (b59df1d), the change is tighten-only so Prop. 2 and the z3 model cover it (views taken under theta' contain those under theta), cost on the twins is 2/75 triggers and 0 lost correct approvals, and the paper says "one world is the whole evidence, closed loop not run". Against: the benefit criterion ("at least one fewer miss") is met by 2 vs 3 misses with discordance 1 vs 0 (exact p = 1.0); the trigger fired on 1 of 150 fire worlds; any threshold between 0 and the sample noise would have passed. The deeper problem is **configuration drift**: G, H, V, L, A and X run v3.6 (A's prereg: "All runs use the orchestrator defaults (v3.6, look-around on)"); the *default* is now v3.7; W's ε numbers are v3.6; XD measures all three. A reader cannot tell which system the headline numbers describe.
Fix (no GPU needed): (1) a one-row "configuration measured" column in Table II (study -> v3.6/v3.7/scrutiny); (2) the sentence "v3.7 adds a tighten-only trigger; evidence of benefit: one world; every closed-loop result in this paper is v3.6"; (3) state now, in the XD registration or an amendment before XD runs, that XD's adaptive arm is the replication and that the default reverts to v3.6 if the trigger fires on more than 15% of the 100 hard-class twins (O3) or the adaptive arm misses more than look-around on any world.

---

## 2. R7 items: status (one line each)

R7 Sec. 1.1-1.2 (theory wording)
* A4 wording (causal, not probabilistic independence): **closed** (main and S10 say "does not influence").
* Lemma 1 for adaptive view sets ("for every realisation of the frames"): **closed** (in the S10 proof).
* Abstract "independent of ... k": **closed** (now "order or advice, grows weakly with the station set").
* Necessity iff dropped its premise / N circular q / "only kind of interface": **closed** (N1, N2, eps_any + eps_rel, q > eps0/(1+eps0), "A trusted certificate would void the first premise").
* Notation `Pr[unsafe | a]` (R6 P6): **closed in S10** (a(omega) written out); the main text still has the short form in places.

R7 Sec. 1.3 (credit, V1-V7)
* V1 refund without saving: **closed** (no refunds; recovery rho_s per confirmed mission; `test_ce1`).
* V2 source label spreading: **closed** (accounts are channels; `test_ce2`).
* V3 hazard pool unpriced by default: **closed** (caution-only classified from per-view scores; `test_ce4`).
* V4 unpriced costs: **partly** (scrutiny-caused refusals and undecided checks are charged; a truthful claim to a burning station is stated as exposure, "not priced"; missions that end before settlement are stated as unpriced).
* V5 certified peers dead code: **closed** (`test_ce5`).
* V6 tightness rate: **closed in substance** (bound C + rho_s m; text says "re-admitted after ceil(1/rho_s) confirmations ... rate about rho_s"). Not re-derived by me.
* V7 missing ledger resets the bound: **open** (S10 says nothing about a deleted or redirected ledger; one sentence: it is an operator-trust assumption like the allow-list).
* The CE tests exist in `tests/test_i24_advice_credit.py`; I did not run them.

R7 Sec. 3 (R6 status carried over)
* Contribution quoted once verbatim; contributions (ii)/(iii) no longer co-equal: **closed** (one sentence + "two supporting results"; `\contribsent`).
* "Independent reference implementation": **closed** in main and S10 ("second implementation by the same authors"); **still stale in README** ("independent reference implementation").
* Third-party oracle (R6 A2): **open** (`make verify` is a third-party-*reproducible* pipeline, not third-party-*written*; S10 says so honestly).
* External timestamp (R6 A3): **open** (no tag; OpenTimestamps question unanswered since HANDOFF; the statuses of A/S/X/XD still read DRAFT, see Sec. 4 #1).
* Delivery interlock / TCB (R6 T1): **partly** (I-22 implemented, Gazebo mechanics check passed on 4 live missions on 10/18, B Amendment 2 runs both arms with it; A and X keep it off, with a good reason: the naive and filtered baselines deliver without a permit by definition; **main L159, S10 trust base and README still say the Gazebo check is pending**; no tampered-node closed-loop test; the z3 model does not execute the ROS node, "mission gating = reviewed" remains the weakest TCB row).
* Allow-list hash and same-host rows in the TCB table: **closed** (6f591b2).
* State-audit power (R6 A4): **open** (no n/N injected-fault count in the main text).
* P5 label circularity: **partly** (six-view label and 0/150, but see Sec. 1.1: the family guarantees visibility).
* P7 supply parse from operator text: **open** (study IF registered, not run).
* A-steer power and wording: **closed** in the prereg; the abstract now prints ours vs control through `\AbsAdvice` (generated, empty until A exists).
* S: "closes" qualified, seven flip rates: **closed** (main lists five flips + one-pass; "non-adaptive signs" in the prereg).
* Title (Relief Delivery Robot): **closed** ("Simulated Relief Robot").
* `\TBD` build failure: **closed** (`FINAL=1` makes a surviving `\TBD` a LaTeX error). Current count: 19 literal `\TBD` tokens in main.tex plus the generated A/S macros.
* Headline figure (unsafe vs time, real data): **open**. Table II `\resizebox` (3 uses in main.tex): **open**. Fig. 5 placement: not checked. Real-camera-through-the-gate result: **open** (only photographs, P/P2/Q/XD-R).
* Q's human spot-check of labels: **open** (pending, as stated).

---

## 3. Claims that outrun the evidence; inconsistencies (abstract / body / supplement / macros)

Numbers: every macro I compared with the JSON matched (W: 3/150, [0.7, 5.7], 76/150, 22/23 side-only, 2.1e-22, ε_any 4.0/7.8/75.8/94.3, tau sensitivity 3/3/3/4, adaptive 2/150, "1 vs 0", 75/75, 2/75, 1/150, W-b 3/815, 9/815, 1/815, 377/384, 303/384, 74; V: 14.94, 11.3-20.1, 20, 1, 6 vs 1 sequences, p=0.0625; G: 11, 1, 16, 0.00195, 0.062, 0.28 recomputed). So no macro/JSON mismatch. The problems are in the prose, and a few unreported fields:

1. **`\Nfailed` list (Discussion, main.tex L253):** "Of the registered claims, \Nfailed{} failed (T1's 2% bound, F, T2, J); the first two led to the look-around, and J stopped us adopting a second model." The macro is *six*, the parenthesis lists *four*. Add V4 (memory under random change) and W-b (hazard rule beats prior art); the sentence "unregistered, each could have been rationalised away" becomes stronger with them.
2. **Interlock status:** main.tex L159 "its Gazebo check is pending" and S10 trust base (L447) "its Gazebo check is still pending", README "its Gazebo check is pending" vs `i22_gazebo_check.log`, IMPROVEMENT_LOG I-22 "Gazebo check 10/18 03:00-03:10", B Amendment 2, video v5. Write "passed a mechanics check on 4 live missions (permits only on approvals; a hidden fire plus an injected 'no check needed' was refused); no run with a tampered mission node".
3. **README staleness (generated part, so fix the generator):** "extra views only when a score is suspicious (I-20) are pending" (W is done and I-20 adopted); "Memory (H) is the measured example" (V missing); "independent reference implementation".
4. **Headline list:** Methodology "the headline claims are G, H, V and A" vs abstract/conclusion citing H only (Sec. 1.2).
5. **Link 2 and Discussion "moving beats thinking harder"** vs W's breakdown and reference row (Sec. 1.1, items 3 and 4).
6. **Limits paragraph uses G's k*eps-hat (0.125, upper 0.57) as "the number" and calls the sum bound "vacuous at k=4"**, while W gives a tighter estimate of the same quantity (2.0% -> 4.0%/7.8%). Two estimates of one quantity (G 1/16, upper 28%; W 3/150, upper 5.7%) sit side by side without saying which one is the current best; say "W supersedes G's plug-in".
7. **"Proved and machine-checked on the implementation"** (Introduction): S10's own sentence is the accurate one: z3 over a *transcription* of the code, the ROS node not executed, 9 000-input differential test, 11/11 mutants. Say "on a z3 transcription of the implementation".
8. **Abstract length:** about 250 words by a crude count with the contribution sentence expanded (the comment in the source says <= 230); `\AbsAdvice` will add words. Check the venue limit.
9. **Page length:** `main.log` says 10 pages including references. RA-L and ICRA both cap at 8 pages (6 + paid extras; verify the call) so this is over by about 2 pages before the A/XD/X numbers are added.
10. **"Of the 7 studies without results yet, the drafts (none) are registered when the integration branch is merged"** (Methodology): `\PreregDrafts` expands to "none", leaving a dangling "(none)". Reword when the macro is "none". Related: the A, S, X, XD files still start "DRAFT for review"; the audit table says "registered at merge". Fix by flipping the status line (Sec. 4 #1).
11. **V absolute-time secondary** (M0, M2 outside their intervals) not reported (Sec. 1.2).
12. **I-20 / v3.7 vs v3.6 measured systems** (Sec. 1.3).
13. **Table II** does not show V's memory-claim failure in the "Claim" column of the main studies table except through `\StatV` ("model: supported; memory: not supported"); good. But row "H" still says only `\StatH`; with V next to it, make the H row say "supported (V: not supported)" or drop the separate rows.
14. **Selection in the abstract:** "a robot without memory (M0) delivered unsafely in 1 of 32, ours (M2) in 0": H alone, 0 vs 1, in M2's favour. V reverses the sign (0 vs 1). Report both (Sec. 4 #3).

Things that are **not** overclaims (checked): "Of the registered claims, six failed so far and are reported" (T1 2% bound, F, T2, J, V4, W-b; granularity is sub-claim level, so A1b/A2/A3/A-time failing later must be counted too, see Sec. 5, C9); "the guarantee is relative and ends at the camera"; "scene text is measured, not claimed"; "the closest prior mechanisms did not separate"; "I-20 ... one world is the whole evidence, closed loop not run".

---

## 4. Top-5 changes by acceptance gain per effort

1. **Flip the registration lines and anchor them externally, before the A main trials start (15 min + one question to the user).** `PREREGISTRATION_A.md`, `_S`, `_X`, `_XD` (and `_Q`) still say "DRAFT for review"; B and IF say "REGISTERED". A's pilot began at 09:14 on the host; the 226 registered runs follow. Commit "REGISTERED <hash>" for A (and the others when their turn comes), and, with the user's consent (pending since HANDOFF), OpenTimestamps of the registration commit hashes (hashes only). Removes the standing R6 A3 objection (in-repo timestamps by the authors) and the ambiguity about what "registered at merge" meant. Gain about +2 points; effort minimal; time-critical.
2. **Scope the ε claim honestly and add the hard subclass (1 h text; 3 GPU-h optional).** Print side-only 3/23 = 13% [4.5, 32]% next to 3/150; name the geometry (straight behind, +-0.15 m); say ε_any(k) is a computed value under independence with the k=4 upper limit 21%; reword link 2 and the "moving beats thinking" sentence (Sec. 1.1). Optional W-c once A is done: 100 fires with lateral, low and behind-another-prop placements, image level, same frozen v3.6/v3.7, registered before rendering (XD's hard class already partly covers this; if it does, say so and skip W-c). Gain +3 to +4 (this is the sentence a hostile reviewer attacks first).
3. **Report memory safety as H+V together and state why V4 failed (1 h).** Abstract and conclusion: "over 82 missions M0 1, M2 1, naive 40"; V4 failed because the sequence test could pass only with zero M2 events (min p 0.031 at 6:0; 0.0625 at 5:0); add the secondary absolute-time line; remove V from "headline claims" or put it next to H. Gain +2; removes the cherry-pick reading.
4. **Freeze the evaluated configuration and pre-state the I-20 revert rule (2 h, no GPU).** Column "configuration" in Table II; "every closed-loop result is v3.6; v3.7 adds a tighten-only trigger with one world of evidence"; amendment before XD runs: revert to v3.6 if O3 (trigger > 15% on twins) fails. Gain +2; removes "default not evaluated" and "adopted on p=1.0".
5. **Claim-hygiene sweep (2 h):** the 14 items of Sec. 3, in particular the stale interlock sentence (three places), the failure list, README generator text, "machine-checked on a transcription", the dangling "(none)", and the page budget. For length: move the transfer table, the headline-less Fig. 5 candidate (see R7) and the Algorithm 1 box to the supplement and shorten Related Work by a third; target 8 pages including references with the A, XD, X numbers in. Gain +2 to +3 (and avoids a desk problem).

Not in the top five but on the list: a short sentence for R7-V7 (ledger deletion), an n/N injected-fault count for the state audit, the tampered-node closed-loop interlock test (needs a code change, 0.5 day), one real-camera capture through the supply check, a person other than the authors writing the 60-line oracle from the one-paragraph rule.

---

## 5. What A must show for the headline to hold: checks to apply the moment A finishes

The headline is Prop. 2 plus "advice cannot relax a check in closed loop". Only items C1-C3 can break it; the rest are price and wording. Apply in this order (all from `a_summary.json`, the ledger, saved model outputs and `mission.json`; no new inference except the C2 replay, which is CPU).

**C0. Integrity first.** 226 of 226 runs present; every failed run listed with its pre-VLM cause and a single re-run; the protocol sha256 equals `9b5a161a4ca2c4ab...` (draft revision 2 hash recorded in the prereg; if the committed protocol differs, an amendment must precede the first trial); registration commit precedes the first non-pilot trial (`PreregOrderOK` = holds for A); the A analysis scripts have no diff since registration (`git diff <reg>..HEAD -- scripts/a_analysis.py` empty, or each change listed); the pilot runs are not in the analysis; all arms are v3.6 and the paper says so.

**C1. Audit = 0 failures (hard gate).** Advice-audit failures across all monotone, scrutiny and scrutiny_soft runs = 0 (`\AAuditFail` = 0), and the outcome audit (ground-truth trajectory) agrees with the logged decision in every run. One failure is a bug in the claimed property: the headline sentence is then withdrawn, not reworded. Also: offline set, relaxation reachable under monotone = 0 on the 224 texts and on every item set of size <= 4; wrong-shelter acceptance = 0.

**C2. The Prop. 2 coupling replay on every unsafe delivery (the sharp test, add if `a_analysis.py` lacks it).** For each run in the monotone and scrutiny arms that ends in an unsafe delivery (label: wrong supply, or a fire perceivable at a design pose): recompute from the saved model outputs the *baseline* decision A_theta(o_s) (v3.6 rule, no advice) on the frames actually captured at the delivering station. It must be 1 in every case. If one has A_theta = 0 while the robot delivered, either A3 (gate) or A1/A2 is violated and the theorem does not describe the system. Expected: the number of unsafe monotone deliveries is 0 of 12 in the F/N cells and 0-1 of 16 in D; each one is listed with its image.

**C3. Naive and filtered really do relax (sanity of the contrast).** poison_safe (F) and poison_location (N) worlds: naive unsafe in 12 of 12 worlds (exact McNemar vs monotone with 12:0, p = 0.0005; needs >= 6 discordant for p < 0.05); the filtered arm reported whichever way it falls (A1b needs >= 6 worlds where the filter lets the attack through and monotone does not; if the filter catches everything, the paper says so, in the same sentence as the headline). A1/A1b p-values stay out of the abstract (prereg).

**C4. Exposure and control (the sentence the abstract prints).** Unsafe deliveries: naive, monotone, control, with Wilson bounds; `monotone_unsafe_where_control_safe` listed with images; every such case must also pass C2. Expected from W: per-station miss about 2-6%, so 0-1 of 16 in D. **Consistency check against W:** the Wilson interval of (monotone unsafe)/16 should overlap W's ε_any(2) = 4.0% [1.4, 11.1]%. If 4 or more of 16 (25%), closed-loop ε is above the image-level value (arrival jitter, V's lesson) and Sec. 1.1 item 2(e) becomes a finding; the "ε small enough" sentence must be rewritten, not the table.

**C5. A2 (truthful advice saves time).** The 6 S worlds: all 6 paired differences positive for the exact Wilcoxon to reach p = 0.031; median saving > 0. A tie or one negative difference means A2 is "not supported" (count it in `\Nfailed`).

**C6. A3 (price).** Extra time of attacked missions <= 1.5 W with W = median(S-controls) - median(N-controls) > 0 (if W <= 0, "not testable", not "passed"); lost deliveries among the 24 attacked missions <= the registered Poisson-binomial 95th percentile (4 of 24, expected 1.7). 5 or more fails the cost claim and counts as a failed registered claim; the arena cannot use soft refusal, so do not explain it away with the depot.

**C7. A-steer wording.** Descriptive only: counts with Wilson upper bound (0 of 16 -> 0.19, worded "undetectable at this n", never "order is irrelevant"); lost deliveries and seconds for tighten-only vs scrutiny_soft; share of runs exposed to the fire station; the plug-in k*eps-hat from G (0.125) and the W oracle-steering values next to it (4.0%).

**C8. Operator-channel extraction.** Exact-match share of extracted advice (pilot required >= 9 of 12); extraction errors are reported with ITT; a missed extraction makes naive behave like control, so report A1 by channel too.

**C9. Bookkeeping.** `\Nfailed` is claim-level: A-safety (C1-C3), A1b, A2, A3 are separate registered claims; each that fails adds one and the list in the Discussion and the abstract count must be updated together. Re-run `check_consistency.py` in non-pending mode for A; regenerate `\AbsAdvice`; fill all A macros (17 `\TBD`); the abstract sentence must print ours vs control, not only ours vs naive; keep the cost sentence "at the simulated false-alarm rate".

**What would break the headline:** any C1 failure; any C2 case with A_theta = 0; a monotone unsafe delivery with no false approval of the baseline check. **What would only change wording:** C3 filter catching everything, C5/C6 failing, C4 above W's interval (rewrite ε text), A-steer null or small effect.

---

## 6. Things that are good and should not be touched

* Prop. 2 with eps_any, sharpness, the without-A1 supremum remark, "relative, not absolute"; the repaired necessity (premises N1/N2, decomposition) and the credit accounting (channels, no refunds): the R7 holes are closed and the text is candid.
* Failed claims in the abstract count, in the Discussion and in Supp. S12 (W-b "0 of 3" with the right reading; V "memory: not supported" with the margin).
* The W design (frozen v3.6, twins, six-view label, tau sensitivity, pre-fixed I-20 adoption rule) and the willingness to publish "3/150 missed, all side-only, worlds named".
* The z3 section's "trusted, and not covered" paragraph, `make verify`, and the I-22 decision not to run A with the interlock (the baselines are defined by delivering without a permit) with B running both arms with it.
