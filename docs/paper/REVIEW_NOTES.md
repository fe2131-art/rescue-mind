# Simulated reviewer report: "Verify, Search, or Stop" (docs/paper/main.tex)

Reviewer stance: critical but fair, ICRA/IROS/RA-L style. Line numbers refer to `docs/paper/main.tex`.
Numbers were taken from `numbers.tex` and `tab_*.tex`. I also read the three pre-registrations, I-09..I-13 of
`IMPROVEMENT_LOG.md`, the last section of `REVIEW_AND_PLAN.md`, `campaign_e_protocol.json`, `make_protocol_e.py`
and `campaign_E_ledger_fire_visibility.json`.
I could not render the PDF figures here (no PDF rasteriser), so figure comments rest on captions, source and file names.

Tentative recommendation: weak reject / borderline as submitted. The evaluation hygiene is unusually good and the
honesty about failures is a real strength. The technical contribution is thin, and the strongest safety claims are tested
only on easy cases.

---

## 1. Summary of the claims

The paper presents RescueMind, a simulated (Gazebo/ROS 2) delivery robot that checks the item at a supply station with a
local Qwen3.5-9B VLM before delivering. The check reads next-token letter probabilities for two permuted multiple-choice
questions and a Yes/No fire question, and it approves only when they agree and clear thresholds. A wrong item triggers a
one-time search of the other station, a hazard stops the robot, and a separate velocity guard keeps the VLM away from the
actuators. On a pre-registered 600-image held-out set the registered rule made 5/408 false approvals (all fires partly hidden behind the supply) and 187/191
correct approvals. In 60 pre-registered closed-loop trials it behaved as expected 60/60 with 0 wrong deliveries. The paper
also reports 14 integration failures found only by running the full stack, and releases all logs.

---

## 2. Major weaknesses (ranked by damage to acceptance)

### W1. The safety-critical case is tested only in its easy form, and the closed-loop result does not test the weakness the paper itself found
**Evidence.**
- Abstract l.33-35 and Results l.228-236 headline 60/60 with 0 wrong deliveries. T1 (l.204-208, Table 1) shows the system
  fails on partly hidden fires: 5/48 false approvals at the registered rule and 3 at v3.5.
- Campaign E uses full-size fires. `make_protocol_e.py` draws `hazard_geom` with scale 0.75-1.0, and
  `campaign_E_ledger_fire_visibility.json` has all 12 fire trials marked "visible". The checkpoint pose is almost identical in
  every trial (about (1.04, 1.0) at the water station).
- That "visible" label comes from the geometric visibility function, which T1 Amendment 2 (l.277-278) shows is wrong under
  occlusion. The paper never says that E contains no hard fire.
- The closed-loop 0/60 wrong deliveries (Wilson upper bound 6%) is therefore compatible with a true hard-case failure rate
  of 5-10% on the hazard stratum. The paper does not say so.
- The "supply check" result (0/332 false approvals, l.204) concerns a trivially separable two-class problem
  (water bottle vs first-aid kit vs empty platform, rendered with the same meshes and fixed geometry as development).
  Nearly all of the safety margin is therefore carried by one Yes/No hazard question, which has no permutation or agreement
  protection. The ablation shows this directly: without the hazard question 47/48 correct-supply fire images are approved
  (Table 2, A3). The headline design (permuted agreement, confidence threshold) is idle for that question.

**Fix.**
- Run the pre-registered campaign F with partly hidden fires, using the magenta-mask labels as the ground truth. The protocol
  `experiments/campaign_f_protocol_design_fire_masks.json` already exists in the working tree but is not in the paper.
- Vary the checkpoint pose. Report hazard recall as a function of visible fire pixels, with a cluster-aware CI (see W3).
- State in the Limitations that E contains no hard fire.

**Feasible in about 1 week with a V100?** Yes. Campaign E took roughly 60 x 104 s of wall clock, so 40-60 new trials take
about 2 hours. Rendering is cheap. The risk is only that the result is worse, which the paper should report anyway.

### W2. The identified weakness is neither fixed nor quantified in the paper, and the planned fix (T2) cannot statistically succeed
**Evidence.**
- The paper's main finding (small or partly hidden fires are missed) has no dedicated result. The size-stratified recall
  (1/7 below 10k px vs 68/69 above, from `REVIEW_AND_PLAN.md`) is absent from main.tex. The body says only "mostly hidden"
  (l.32, l.206-207).
- The repo's own correction (commit 7c2955e) says 3 of the 5 false approvals were below 10k px and 2 were at 13-15k px, and
  that all were "partly hidden". main.tex still says "mostly hidden" in the abstract (l.32) and at l.206-207. At 13-15k px
  the fire is roughly 4-5% of the frame, which is not "mostly hidden".
- The size cut at 10k px was chosen after looking at T1, so it is post hoc. The paper must say so.
- T2 (`PREREGISTRATION_T2.md`) is a fresh draw from the T1 distribution. At T1 rates only about 7 small visible fires occur per
  600 images, and v3.5 makes about 3 false approvals. An exact two-sided McNemar test with 5 discordant pairs all in one
  direction gives p = 0.0625, so P1 ("fewer false approvals, p<0.05") cannot succeed unless there are at least 6 discordant
  pairs. P1 is underpowered by construction.
- I-13 added DH2 after seeing intermediate DH results (log, "追記"). The rule is unchanged, but this is a researcher degree of
  freedom that the paper should disclose if I-11/I-13 are mentioned. The paper currently mentions neither tiles/h36 nor the
  Clef-Flash second model, and nothing about T2.
- The fixed rule chain (T1 -> I-11/I-13 -> T2) must not be reported selectively. If T2 is run, its result must appear in the
  paper whatever it is.

**Fix.**
- If T2 has not yet been scored, amend the registration before scoring. Oversample small and partly hidden fires, for example
  by merging the DH2 generator parameters into a T2 stratum, and set the primary test on hazard recall in that stratum, not on
  the whole-set false-approval count.
- Report the T1 size-stratified recall, labelled post hoc.
- Fix "mostly hidden" to the measured pixel statistics.
- Add a sensing-side fix that actually addresses occlusion (a second viewpoint, see Section 6), since a better prompt cannot see
  pixels that are not in the frame.

**Feasible?** Yes (T2 amendment: hours; rendering an enriched set: under 1 day; scoring: minutes on the V100).

### W3. Statistics treat 600 correlated images as independent, and the "held-out" sets share the development distribution
**Evidence.**
- l.186-188: Wilson intervals and McNemar tests are applied per image. T1 has 60 worlds x 2 stations x 5 viewpoints, so the
  images are strongly clustered. There are only 16 fire worlds, and the five false approvals presumably come from a handful of
  them.
- The reported 408-image CI [0.5, 2.8]% is too narrow. The effective sample for fire is roughly 16 worlds (48 images). The same
  applies to the McNemar stars in Table 2 and to the rates in Table 1.
- The T1 images come from the same generator family, the same meshes, the same fixed station geometry and the same camera as
  development. "Unseen" is limited to continuous lighting and offsets, plus two new distractors (a crate and a cone,
  l.164-167).
- The Limitations (l.282-285) concede the domain gap but never quantify it. The abstract (l.29) says "unseen lighting, object
  placement and distractors", which suggests more novelty than exists.
- Campaign strata are small (4-12 trials, Table 3). 60/60 is dominated by the authors' choice of stratum mix.

**Fix.**
- Report cluster (world-level) bootstrap or exact cluster-adjusted intervals, and the number of distinct worlds behind each
  count.
- Add a clearly out-of-distribution test: new object meshes or textures, a different camera height or field of view,
  and a different arena.
- Add a small real-image check (see W5).

**Feasible?** Yes. The cluster bootstrap takes hours. A new-mesh or camera set takes 1-2 days in Gazebo.

### W4. No competitive baselines and no ablation of the system claims; the only "baselines" are definitional
**Evidence.**
- B0 (blind delivery, l.234) is wrong in every swapped, empty and fire trial by construction: 16 + 12 + 12 = 40. The figure
  "40" in the abstract (l.34) therefore measures the authors' stratum mix, not any property of the system. It is a
  counterfactual computed from logs, not an executed baseline (l.284 acknowledges this).
- B1 is the authors' own earlier version.
- No non-VLM baselines. For a two-class item check on a clean platform, a CLIP zero-shot classifier, an open-vocabulary
  detector or a small CNN would very likely also reach 0 false approvals. For fire, colour and segmentation baselines are
  trivial in a simulator that supplies masks. The claim that a VLM is needed is untested.
- No ablation of the claimed safety contributions in closed loop: the velocity guard (what does it intervene on? how often?
  any obstacle or sensor-dropout trials?), the recovery policy, the search-after-hazard rule.
- The "Simplex-style" guard (l.58-60, l.152-155) has no safety evaluation. The one experiment is 2/2 vs 2/2 on a
  stall-injection test (l.267). The guard also protects only motion, whereas the failure mode the paper studies is a
  perception error on the checkpoint, which no guard covers.
- Within T1, the larger model is not better: Qwen2.5-VL-3B ties the 9B on false approvals (4 vs 5) and correct approvals
  (187 vs 187) (Table 1). Qwen3.5-9B was chosen on a development set where three models scored 176/176 (Table 5, Appendix)
  and the tie was broken by explanation accuracy and by a 2-utterance difference in unsafe intent (l.301-303). Neither of
  those two criteria affects the checkpoint decision.
- A2 (question 2 only) has fewer false denials than the full rule for the 9B (1 vs 4, Table 2) with the same false approvals.
  A4 (no threshold) is identical to the full rule for all four models. The data therefore show that, for the 9B, neither the
  permuted agreement nor the confidence threshold helps, and agreement costs 3 extra false denials.
- The abstract's "sufficient confidence" (l.24) and the Eq. 1 threshold $\tau_s$ are not supported by any result.

**Fix.**
- Add executed baselines on T1/T2 (and in a rerun of part of E): CLIP/SigLIP zero-shot with the same thresholds, an
  open-vocabulary detector (OWL-ViT or similar), a fire and smoke segmentation head trained on the DH/DH2 dev masks, and a
  conformal (KnowNo-style) threshold calibrated on dev.
- Run a closed-loop ablation: guard off or injected obstacle and sensor-dropout trials; recovery off.
- Reframe the finding honestly: the rule's value is model-agnostic robustness to a weak model (3B: 36 false approvals for
  question 2 alone, 4 with agreement), and the 9B is not required.

**Feasible?** Yes for the T1/T2 baselines (CLIP or SigLIP on a V100 is minutes; a small segmentation net trained on 600 dev
images takes hours) and for a 20-30 trial guard stress test. A conformal threshold is an offline script. A KnowNo
re-implementation is not needed, only the same-calibration comparison.

### W5. Sim-to-real, "on board", and the deployment story are unsupported
**Evidence.**
- The abstract (l.20-21) says "running entirely on board". The experiments run FP16 9B (18 GB VRAM) on a V100 32 GB server GPU
  in the same container as the simulator (l.112). No edge-hardware, quantised or power-capped measurement exists.
- The fire is a stylised emissive particle effect (l.283). Real smoke, glare, lamps, sunsets and steam are untested, and the
  only fire-like distractor is an orange cone. A 0/523 false-alarm rate (l.203) with $\tau_h = 0.05$ says little about
  availability in a real shelter, where a false hazard stops the whole delivery.
- The justification "a false alarm only stops the robot" (l.143) ignores the cost of stopping in an emergency. No false-stop
  rate was measured on realistic distractors.
- The robot has no manipulator and no handover. "Delivery" is driving to a shelter coordinate with known station positions
  (l.116-125), so the integration contribution is smaller than the framing suggests.

**Fix.**
- Evaluate the frozen rule offline on real photographs: public fire and smoke images (for example D-Fire) plus fire-like
  negatives (lamps, sunsets, orange vests), and phone photos of real water bottles and first-aid kits on shelves or tables.
- Report the 9B in INT4 or INT8 (VRAM and latency on the V100, optionally at a capped clock) and drop "entirely on board" or
  qualify it as "on-premise".

**Feasible?** Yes. These are offline image evaluations, 1-3 days. A real-robot run is not possible and is not needed if the
claims are narrowed.

### W6. Novelty is thin and positioned against the wrong class of work
**Evidence.**
- Each ingredient has a precedent the paper itself cites: closed-set letter scoring (SayCan, KnowNo, Robinson et al.),
  option permutation (Zheng et al., Pezeshkpour & Hruschka), consistency checks (Wang et al.), Yes/No polling (POPE), selective
  classification (Geifman & El-Yaniv), Simplex (Seto, Sha).
- The REFLECT/AHA/success-detector comparison (l.71-77) is a category mismatch. Those works explain or detect task failure
  after execution, in manipulation. Verifying "is this the right object on the shelf" is a recognition task, and the right
  comparators are pre-condition checks and VQA-based verification (see Section 4).
- The paper's strongest contribution is the audited, pre-registered evaluation and the failure log. The abstract and
  conclusion (l.290-293) put the method first.

**Fix.** Reposition as a case study and evaluation-methodology paper (or a "lessons" paper), and state the novelty as the
*protocol* (ground-truth audit, mask-based labels, amendment discipline), not the scoring rule.

**Feasible?** Yes (rewrite).

### W7. "Pre-registered" is stronger than the evidence allows
**Evidence.**
- l.27-28 "all evaluations were pre-registered". The registrations are Markdown files in the authors' own repository, with no
  external timestamp (OSF, signed tag). The paper gives no commit hashes.
- T1 has three amendments. Amendment 2 (labels redefined from a second render) was made after viewing a contact sheet of fire
  images. Amendment 3 changed the system under test ($\tau_h$ from 0.5 to 0.05) after a pilot failure and registered it as
  a "pre-specified secondary".
- The hazard threshold $\tau_h = 0.05$ was set from 164 fire-free dev images (max $p_h = 0.0007$) and one pilot trial. The
  threshold-versus-recall trade-off on T1 is not shown. Why 0.05 and not 0.005? No analysis of $\tau_h$ is given.
- Not every evaluation has a registration: the instruction parser's 60 utterances, the guard experiments, the timing table
  and the DDS probes are not in the registered files I read. "All evaluations" is overstated.
- The abstract mixes versions: T1 numbers are for the registered v3.4 rule (5/408), and closed-loop numbers are for v3.5.

**Fix.** Say "primary endpoints of T1, E and (if reported) T2 were registered; exploratory analyses are labelled". Cite
commit hashes and mirror the registration to an external timestamp (OSF or Zenodo) before submission. Report T1 for v3.5 in
the abstract alongside v3.4.

**Feasible?** Yes (hours).

### W8. The instruction-parsing result is weakly supported and off-topic
**Evidence.** l.244-247: 55/60 for the hybrid parser vs 31/60 for TF-IDF trained on 40 synthetic utterances is a straw-man
comparison. "0 unsafe acceptances" has no denominator (how many utterances should be refused?), so there is no interval. The
section dilutes the paper.

**Fix.** Move it to the appendix with the denominator and CI, or cut it. Add a fair keyword or rule baseline.

**Feasible?** Yes (hours).

---

## 3. Overclaims or statements the data does not support

| Where | Sentence (quoted) | Problem / contradicting number |
|---|---|---|
| l.22-24 | "The robot approves only if both questions agree with sufficient confidence" | A4 (no threshold) gives identical errors for all four models (Table 2), so the confidence threshold has no demonstrated effect. Agreement does not reduce false approvals for the 9B (A1/A2 = 5, same as full). |
| l.26 | "Motion stays behind an independent velocity guard that the VLM cannot command." | True by construction, but no experiment shows the guard preventing a harmful event. It does not address the perception failure that causes every false approval. |
| l.27-28 | "all evaluations were pre-registered" | See W7. Parser, guard, timing and DDS experiments are not registered. T1 had three amendments. |
| l.29-32 / l.206 | "Every false approval was a fire mostly hidden behind the supply." | Per the repo's own correction (7c2955e), 2 of 5 were at 13-15k fire pixels and only 3 were below 10k. "Partly hidden" is the supported wording. Also, 5 at the registered rule but 3 at v3.5, so "every false approval" refers to the superseded rule in the abstract. |
| l.34 | "A blind-delivery baseline would have made 40." | Definitional: 16 + 12 + 12 faulted trials by construction (W4). Not evidence for the method. |
| l.20-21 | "running entirely on board" | Experiments use an 18 GB FP16 model on a V100 server GPU in the simulator container. No edge hardware. |
| l.58-60, l.152 | "Simplex-style separation" | A Simplex architecture needs a verified safety controller plus switching logic. Here a hand-written velocity filter is evaluated by a 2/2 vs 2/2 test (l.267). Limitations (l.286) concede it is not formally synthesised. |
| l.208 | "The registered claim of fewer than 2% false approvals is therefore not supported" | Honest and good. But then the abstract (l.29-32) and conclusion (l.290-291, "A local VLM can serve as a fail-closed gate") present the result positively, with no mention that the target was missed or that hazard recall is only 67/76 (88%). |
| l.211-213 | "which is the option-letter bias of [Zheng et al.] in action" | No letter-distribution analysis is given. The 36 false approvals of question 2 alone could equally be a prompt-wording effect (the "A: neither" option is first in q2). Causal attribution is asserted, not shown. |
| l.217 | "All models missed largely the same small fires" | No overlap statistic given (e.g. Jaccard, shared misses). Also the text prints "from 59 to 68/76" because `\THazMin` has no denominator. |
| l.257-258 | "Free-form JSON from the VLM was unusable" | Table 1: 9B free JSON has no parse errors (l.214-215), the same 5 false approvals, and 158/191 correct approvals vs 187. That is a 15-point loss of availability, not "unusable". The 21/48 parse failures were an earlier, smaller model. |
| l.215-216 | 3B free JSON "57" correct approvals, 148 of 1200 unparsed | Presented as a failure of free-form output, but a model that approves 30% of correct cases and 0 false approvals is just a conservative classifier; the baseline has no threshold, no permutation and no consistency check, so it is a straw man. |
| l.143 | "a false alarm only stops the robot" | Cost of false stops is never measured, and fire-like negatives are limited to a cone. 0/523 false alarms has an upper bound of about 0.7% on synthetic fire-free scenes only. |
| l.250 | "revealed problems that 506 offline unit tests ... had not" | Plausible but anecdotal. The generalisation that mocks cannot find these bugs is not supported by a counterfactual, and one of the "14 failure causes" (the wheel-axis frame) is a model-description bug, not a VLM-system finding. |
| l.35 / l.66 | "14 failure causes" | The paper lists about 7 bullets; the 14 enumerated in `FINDINGS.md` are not in the paper. A reader cannot check the count. |
| l.228-233 / l.35 | "behaved as expected in 60/60" | "Expected" is defined by the authors per stratum. 12 fire trials are all full-size, clearly visible fires (W1). 60/60 is not evidence of robustness. |
| l.170 | "The 1 ambiguous images are excluded ... as registered" | The registration expected 14 (amended 10); with mask labels 1 remains. Fine, but then the 21-613 px band is nearly empty, which means the fire-size distribution is bimodal and unlike realistic incipient fires. The 614 px (0.2%) visibility cut is the authors' choice and not defended. |

---

## 4. Missing baselines and related work (novelty check)

**KnowNo (Ren et al., 2023).** Closest relative; the paper handles it fairly (l.78-82), but the difference is overstated.
- KnowNo's response to uncertainty is to ask for help. "Refuse or search" is a different action space, not a different
  method. Without the conformal calibration, the paper loses KnowNo's coverage guarantee and gets nothing in return except a
  hand-set 0.5. It should be compared against a conformal threshold (calibrated on dev, evaluated on T1/T2) on exactly the same
  scores. This is the obvious reviewer request.
- Option permutation as a debiasing step is Zheng et al.'s PriDe idea. "Agreement" is a 2-sample vote. Both are acknowledged,
  but the paper's novelty paragraph (l.81-82) should say plainly that no new scoring method is proposed.
- The A2 and A4 ablations show that, for the strongest model, neither permuted agreement nor the threshold helps. So the one
  KnowNo-vs-us difference you claim is not demonstrated.

**REFLECT / AHA (failure explanation).** Different problem (post-hoc explanation of manipulation failures; AHA is fine-tuned).
They are not baselines, and positioning "we run before acting" against them (l.76) is a category mismatch. The paper should
instead compare to pre-condition and affordance verification and to work that uses VQA probabilities for success detection.

**VLM-based success detection.**
- Du et al. (cited) frames success detection as VQA. The paper's check is the same formulation applied to pre-condition
  verification, and the novelty over it is only the zero-shot, thresholded, audited use.
- Inner Monologue (cited) uses passive scene description and success detection feedback; the recovery policy is a small
  cousin of that.
- Not cited, and I would expect: Sinha et al. (RSS 2024), real-time anomaly detection and reactive planning with LLMs, and
  Elhafsi et al. (2023), semantic anomaly detection with LLMs. Both are close to "use a foundation model as a runtime monitor
  with a safe fallback".
- Not cited: Whitehead et al. (ECCV 2022), *Reliable Visual Question Answering: Abstain Rather Than Answer Incorrectly*. This is
  the direct selective-VQA precedent for thresholding a VLM's answer confidence.
- Also worth checking and citing if verifiable: VLM-as-value or success-signal work (for example GVL, in-context value learning),
  and recent robot-safety constitutions or benchmarks for foundation-model robots (for example the Gemini Robotics safety
  work), as alternatives to the guard.
- Not cited though present in `related_work_notes.md`: Introspective Planning (Liang et al.), VLMaps, Delmerico et al. If they
  are not used, drop them from the bib; if they are relevant (Introspective Planning is), add them.

**Missing baselines in the experiments (see W4).** CLIP or SigLIP zero-shot, an open-vocabulary detector, a trained fire and
smoke segmenter on dev masks, a conformal/KnowNo-style calibrated threshold, a single-question variant of the closed-loop
system, and an executed (not counterfactual) naive pipeline.

**Domain.** Humanitarian logistics is cited (Balcik; Murphy), but no related robotics work on delivery verification,
warehouse or inventory auditing (for example robot-based stock checks) is positioned against. A reader cannot tell how this
differs from a standard "verify the pick" step in warehouse robotics.

---

## 5. Clarity and structure

**What a reader cannot follow.**
- The system version history leaks into the text. v3.4 vs v3.5, "registered" vs "pre-specified", $\tau_h$ 0.5 vs 0.05, and
  "campaign D / E" (l.142, l.173-174, l.198-203) force the reader to track three configurations. Define one main system
  (v3.5), call v3.4 a "pre-registered primary" once in a short table, and give both thresholds in one place.
- Eq. 1 (l.139) uses $p_{h,k}$ with $k \in \{1,2\}$, i.e. a hazard probability per pass, while l.134-137 describes one hazard
  question $q_h$ and $p_h$. Table 4 says "4 scored queries" (2 MC + 2 hazard), while the text implies 3. The I-11 log says
  the hazard question is cached per image. State exactly how many forward passes and what $p_h$ means.
- The prompt text is given only for the hazard question. The two MC prompts and the Japanese/English instruction are not
  shown; put them in an appendix or a small table. "Tokenizer variants" (l.136) is not explained.
- The `\emph{visible}/\emph{hidden}` thresholds (614 and 20 px, l.169) appear without justification. Say how they were chosen
  and show the pixel-count histogram.
- "Fire mostly hidden" is used qualitatively. The reader needs a plot of detection vs visible fire pixels (log x-axis), with the
  five false approvals marked and the 10,000-px cut labelled post hoc. This is the single most informative figure the paper
  does not have.
- The viewing distance and viewpoint range of T1 (five viewpoints) are not given. `REVIEW_AND_PLAN.md` says all false denials
  are at 0.85-0.94 m, and the real robot would stop at about 1.4 m. This is not in the paper.
- Search policy: "the other station once" with a two-station arena (l.148-149) is a very small recovery problem; say so.
- l.173: "three controlled scenes plus fire, dim light and a box". Campaign D is hard to reconstruct from this. A table
  of strata for D parallel to Table 3 is needed.
- The authors' names and repo (l.14): "Anonymous Authors" with a non-anonymous GitHub URL that reveals the account. Fix for a
  double-blind venue, or drop "Anonymous".

**Figures and tables.**
- Fig. 3 (risk-coverage, l.219-221) sweeps $\tau_s$ with $\tau_h = 0.5$. That is the superseded hazard threshold, and A4
  shows $\tau_s$ barely matters. The curve is nearly flat and not informative about the real trade-off. Replace it with a
  curve over $\tau_h$ (false approvals on fire images vs false alarms on fire-free images) for the final system.
- `fig_t1_examples.pdf` exists in the folder but is not included in main.tex. There is no image anywhere in the paper
  showing a rendered station, a false approval, or a hidden fire. For a perception-safety paper this is a significant
  omission. Add a 2 x 3 panel: nominal, swapped, empty, cone, visible fire, the failing hidden fire with the mask overlay.
- Fig. 4 (E trajectories, l.224-225) shows ground-truth paths coloured by outcome. All 60 outcomes are "correct", so the figure
  carries no information beyond "robot drove to the shelter". Replace it with something that carries signal (guard
  interventions, time-to-stop after a refusal, per-trial latency).
- Table 1: columns need units or denominators on "s/pass", the 3B VRAM is missing in Table 5 ("--"), and the free-JSON rows
  have dashes without explanation. Report false denials in Table 1, not only in Table 2. FD for 3B-v3.5 (30) is hidden in a
  secondary table.
- Table 2: the star means "significantly different from the full rule", but a star on a worse result (3B v3.5 FD 30) is
  easy to misread as an improvement. Separate FA and FD columns and mark direction.
- Table 3: the "Condition" column mixes distractor types and fire. Add the number of distinct worlds, per-stratum Wilson
  CIs (all upper bounds are wide for n = 2-12), and an explicit note that fire is clearly visible.
- Table 4 (timing): "drive to shelter" has median 24.8 s and max 25.3 s but min 15.0 s, so the distribution is bimodal
  (probably station-dependent). Report by station. The claim "the check is short compared with driving" holds, but a
  safety-critical stop of about 5 s should be compared with a realistic 1-2 s budget for a mobile platform.
- Numbers formatting bugs: `\THazMin` is "59" without "/76" (l.217), so the text reads "from 59 to 68/76".
- The Failure Analysis section (l.249-279) is a list of anecdotes of very uneven weight (a QoS drop, a Linux capability issue and a safety
  threshold are given similar space). Group them into "simulation validity", "middleware", "decision logic", and say which
  are specific to VLM gating. The wheel-axis finding is important for any audit-by-odometry paper; keep it. The
  `LD_LIBRARY_PATH` secure-mode anecdote (l.268-269) is not a research finding.

---

## 6. The three changes that would most increase the chance of acceptance

**1. Test and fix the hard hazard case (W1, W2). About 4-5 days.**
- Run the pre-registered campaign F with partly hidden, small fires (F protocol already exists in the tree). Vary the
  checkpoint pose.
- Add a sensing-side mitigation that addresses occlusion directly: a second capture from a lateral offset (for example +/- 0.3 m
  or an arc), refusing if any view triggers $p_h \ge \tau_h$. Compare it with the model-side fixes (tiles, h36, Clef-Flash).
- Amend T2 before scoring so that it has power: oversample small visible fires, and state the primary endpoint as hazard recall
  in that stratum with a cluster-aware CI. An exact McNemar P1 on about 3-5 false approvals cannot reach p<0.05.
- Report the size-stratified recall (labelled post hoc) in the paper, correct "mostly hidden", and include the T2 result
  whatever it is.

**2. Add real baselines and cluster-aware statistics, and narrow the claims (W3, W4, W6, W7). About 2-3 days.**
- Executed baselines on T1/T2: CLIP/SigLIP zero-shot, an open-vocabulary detector, a mask-trained fire segmenter, and a
  conformal (KnowNo-style) threshold. Show where the VLM's agreement design adds something and where it does not.
- A closed-loop stress test of the guard (injected obstacle, sensor stall) so that the "independent guard" claim has data.
- World-level bootstrap CIs. Drop or soften "Simplex", "all evaluations were pre-registered", "on board", "sufficient
  confidence". Reposition the paper as a pre-registered, audited case study with a model-agnostic checking rule.
- Show that 3B and 9B tie, and discuss deploying the smaller model.

**3. Close the sim-to-real gap as far as possible without a robot, and fix the presentation (W5, Section 5). About 2-3 days.**
- Offline evaluation of the frozen rule on real photographs: public fire and smoke images plus fire-like negatives, and phone
  photos of real water bottles and first-aid kits. Report false-alarm and false-approval rates, even if the result is
  mixed.
- INT4/INT8 latency and VRAM on the V100, and replace "on board" by what was measured.
- Presentation: one system version in the main text, a figure of rendered images (use `fig_t1_examples.pdf`), the
  detection-versus-fire-pixels plot, a $\tau_h$ curve instead of the $\tau_s$ curve, the missing prompts, Eq. 1 and the
  query count made consistent, the `\THazMin` bug fixed, and the repository URL anonymised if the venue requires it.

---

### Fair credit (to keep the report balanced)
- Honest reporting of a missed pre-registered claim (l.208), of aborted campaigns and of amendments.
- Ground-truth auditing that exposed the odometry bug (l.252-255).
- Mask-based fire labels that replace a geometric label that was found to be wrong.
- Reproducibility: seeded specs with hashes, and every number generated by a script.
These are above the usual standard for simulation papers. They do not compensate for the narrow difficulty of the tested
cases, but they are the paper's best framing, and the revised submission should lead with them.
