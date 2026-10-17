# Simulated reviewer report, round 2: docs/paper/main.tex (13 pages, IEEEtran)

Stance: critical but fair, ICRA/IROS/RA-L. Line numbers refer to the current `main.tex`. Numbers come from `numbers.tex`,
`tab_*.tex` and the registrations `experiments/PREREGISTRATION_{H,J,R,Z,P,P2}.md`. H, J and R are still `\TBD`, so I judge
design and claims, not outcomes. I did not read the unpublished result files.

Tentative recommendation: borderline, leaning weak reject for 8 pages as it stands; weak accept for a focused version.
The hidden-fire problem is now handled well (F, G, size figure, honest negative results). The paper has grown from one
case study into four loosely coupled contributions (check, look-around, memory, two-AI), and the two newest ones (memory,
Jev) are the weakest.

---

## 1. Round-1 weaknesses: status

| # | Status | Evidence |
|---|---|---|
| W1 hard fires untested in closed loop | **Largely addressed** | F, G, H, J use small partly hidden fires with mask labels (Sec. VI-C, Fig. 7, Table I). Still open: E (60/60) is full-size fires only and is still the abstract headline; checkpoint pose is not varied; fire is stylised (Limitations). |
| W2 weakness neither quantified nor fixed; T2 underpowered | **Addressed** | Size-stratified recall (`\TLargeDet`, `\TSmallDet`, Fig. fire_size), wording changed to "partly hidden" (l.386), sensing fix (look-around, 11 to 1, p=0.0019), T2 reported although uninformative (l.436-444). Residual: the 10 000 px cut is still not labelled post hoc, and the 68/69 vs 1/7 split is v3.5 while the sentence around it is about v3.4 (see 3.2). |
| W3 non-independent statistics, no OOD | **Partly** | World-cluster bootstrap added (`\TFACluster`, R, Methods). No OOD test (new meshes, camera, arena); Table E has no worlds or CIs per stratum; G conditions on a ground-truth label that includes the side views (see N5). |
| W4 baselines and ablations | **Partly** | Study Z executes SigLIP/CLIP (Table Z); text now says openly that permutation and threshold do nothing for the 9B (l.396-398). Open: no detector, segmentation or conformal baseline; Z's CLIP is a straw man (see 3.1); B0 = 40 is still definitional and still in the abstract (l.35); no guard stress test; no small-model deployment discussion (3B ties 9B). |
| W5 sim-to-real, "on board" | **Partly** | "On board" is gone; R (degradations) and P (real photos) added. But P exposes 64% false alarms, which the abstract and conclusion do not carry (N2). "Runs on the robot" (l.46) still means a simulated robot. No INT4/edge-hardware numbers. |
| W6 novelty and positioning | **Partly** | Related work now covers monitors, memory, active perception; REFLECT/AHA are placed correctly as post-hoc explanation. New problem: novelty is spread over four items, each thin (N3). |
| W7 "pre-registered" overclaim | **Partly** | Appendix B audit with commit hashes; abstract softened. Still: no external timestamp, studies chained on the same day (2026-10-16/17), T1 Amendment 3 changed the system. Table I caption says "Each was registered before its first trial" while C is excluded and parser/guard/timing are not listed (N6). |
| W8 parser result weak | **Open** | Sec. "Instruction parsing" unchanged: TF-IDF straw man, "0 unsafe acceptances" without a denominator or CI. Move to supplement or cut. |

---

## 2. New major weaknesses, ranked

### N1. Mission memory: Proposition 1 is correct but trivial, and campaign H is partly built to produce its own result
**(a) Proposition 1 (l.264-278).**
- Correct as stated. The approval is a conjunction. Raising a threshold or adding a conjunct cannot turn a 0 into a 1.
  "Order does not change a conjunction" is also right. It is a one-line observation about monotone Boolean functions, not a
  result. Calling it a proposition and writing "we prove" in the abstract (l.41) invites the reviewer reaction "is that all?".
- Its content is carried by the premise, not by the proof. The premise is exactly what the code enforces
  (`apply_memory_caution` only tightens). So the claim reduces to "we wrote the code so that it only tightens".
  Two of the three hypotheses are vacuous in this design: memory never changes $\taus$ and never removes views, so only
  $\tauh'=0.01\le0.05$ is used.
- The statement hides three gaps:
  1. "For every $o$" fixes the observation. A different route, a different side order (early stopping at the first
     hazard) and a different pose produce different frames. The paper concedes this (l.277) but then still claims
     safety "at the mission level" through H.
  2. Route reordering changes *exposure*. Take one bad and one good station. Checking the good one first gives
     near-zero unsafe probability. Checking the bad one first gives probability $\varepsilon$ (the per-check false-approval
     rate). Stale memory can put the bad station first where the memory-free default would not. So per-check monotonicity does **not**
     imply mission-level monotonicity, and P3 (M2 $\le$ M0) is an empirical hope, not a corollary.
  3. The two-model rule has its own thresholds (0.65, 0.80, Jev hazard) that are outside $\theta$.
- Is it non-trivial enough? Not as a theorem. Suggested fix, in order of value:
  1. Demote it to "Observation / design invariant" and say "immediate".
  2. Add the mission-level bound that is actually true and useful: unsafe probability $\le \varepsilon_{\max}\cdot E[\#\text{bad stations visited}]$, plus a
     statement that memory affects only the exposure term, never $\varepsilon$. Then H and the change-rate model become a
     test of the exposure term. That is a real, falsifiable statement.
  3. Add the cost side: caution at $0.01$ increases false refusals. A bound or measurement of that cost is the missing half
     of the invariant (see N2 for why 0.01 is a risky number).
  4. State what the audit (recomputation) adds beyond the proof: a runtime check of the premise.

**(b) Is campaign H a straw man?** Partly, yes, and a reviewer will say so.
- Naive memory M1 skips the on-site check and look-around whenever memory says "supply seen, no hazard". Three of the four
  scripted stories (relocation change, fire appears, fire disappears and a new one appears) change the world between
  missions with probability 1. Under such a script M1's unsafe deliveries are nearly determined by the script: every
  change story after a "good" memory yields an unsafe delivery by construction. The McNemar p-value for P2 (M2 vs M1)
  therefore measures the story mix chosen by the authors, not a property of memory.
- P1 (speed-up) is evaluated only on the 8 *relocation_persist* missions, i.e. exactly the stories in which memory is
  right. P2 is evaluated on the mix in which memory is mostly wrong. Each endpoint selects the stratum favourable to the
  claim. The headline requires P1 and P2 jointly, which makes it look balanced; the structure is not.
- M1 is a policy that never verifies once it has seen something. Published memory systems (ReMEmbR, Embodied-RAG, KARMA)
  are not used this way for safety-critical acts. The Discussion says "the naive policy is not a straw man" (l.589), but gives
  no citation or practical example of such a system.

How to defend it (all possible without new robot time except the last):
1. Reframe H as a **stress test with a known answer**, not a comparison of equals: "what does staleness cost per
   event, and where is the break-even change rate?" The change-rate model (Fig. hrate) is the right headline, because it does not
   depend on the story mix. Put the break-even $q^\ast$ in the abstract and give a CI from the measured per-check rates.
2. Say in Methods that the stories are chosen so that every transition type occurs equally often, report each story's
   result separately (the secondary "by transition" table is already registered), and do not report a pooled
   M1-vs-M2 p-value as evidence. Keep the p-value, but label it "by design".
3. Add a **fair intermediate baseline** M1b: age- or confidence-aware trust. For example skip only the look-around, or skip
   the check only if the memory is younger than $T$ missions. This is what a practitioner would deploy. If M1b is also
   unsafe at realistic $q$, the argument is much stronger. If M1b is safe and fast, the paper must say so and
   the contribution shrinks to "a proof-friendly variant".
4. Report the honest wins of M1: it is fastest and correct in `fire_persists` and `relocation_persist`. The existing
   registered secondary table does this. Show it in the main text so the reader sees the trade-off, not a fall.
5. Report $M2$'s own failure cases: missed small fires (the ~1/16 from G) and false refusals from caution. P3 only tests
   that M2 is not worse than M0.
6. If time allows (small): add a no-change story pair (all missions persist) so the table contains a world in which M1 is
   strictly better than M0 and M2 is near M1.

### N2. Study P (64% false alarms) is in tension with the "fail-closed and useful" story
- The numbers: recall 298/300 (99.3%), false alarms 64/100 at the frozen $\tauh=0.05$. A classifier that refuses everything is
  also "fail-closed". The paper makes exactly this argument against CLIP in Z (l.404: "CLIP refused almost everything"). The same
  logic applies to the paper's own hazard question on real photographs.
- The paper treats this as "the safe direction" (l.505-507) and a "deployment prerequisite". That is honest but, in
  context, it undercuts several claims:
  - The abstract and conclusion ("A local VLM can serve as a fail-closed gate") do not mention P. The reader of the abstract
    sees 0/523 false alarms (simulation) and no number from real images. The 64% belongs in the abstract.
  - $\tauh=0.05$ was chosen from rendered fire-free images (max 0.0007) and one pilot. Real everyday scenes score
    $p_h\approx0.01$ (l.504). The memory-caution threshold $\tau_h^{\mathrm{mem}}=0.01$ (l.261) is therefore at the level of
    ordinary real scenes: remembered hazards would stop the robot on almost any outdoor view. This contradicts "caution is
    cheap".
  - Look-around multiplies the exposure: each approval now faces three hazard tests (front and two sides). With a per-image
    false-alarm rate in the tens of percent on real data, the availability of the full system on real images could be
    close to zero. "No false stops" (l.38) is 0/8 per arm in simulation (Wilson upper bound about 32%).
  - Hard negatives are from fire-surveillance cameras (haze, clouds); a supply station is a different distribution.
    That argues the 64% may be pessimistic, but the paper cannot tell which way it is biased. The post hoc remark
    about "streets, beaches and roads" has no sample size.
- Recommendations:
  1. Report ROC / AUROC and precision at fixed recall on P and P2 together, not one operating point. State the operating point
     where recall is $\ge 0.95$.
  2. Include P2 (site calibration, already registered, Amendment 1 moved the calibration set to all nine shards) in the main text
     with its pre-stated claim (recall $\ge$ 0.90 and false alarms $\le$ 0.20). If it fails, say that the real-image
     false-alarm problem is unsolved. If it passes, say that it passes on D-Fire only.
  3. Reword the claim from "fail-closed gate" to "fail-closed by construction; availability on real imagery requires site
     calibration, shown on D-Fire to give X". Do not use "useful" without the calibrated number.
  4. Check the D-Fire licence at the original repository. A Hugging Face mirror tag "CC0" does not grant rights to scraped
     web images (see 3.4).

### N3. Scope creep, version zoo and length
- Contributions in the abstract: check, look-around, memory with proof, camera degradation, real photographs, two-AI design,
  failure log, audited evaluation. Each is credible but none is deep. The current abstract is about 380 words.
- Naming collisions: v3.3, v3.4, v3.5, v3.6; "configuration B"; arms A/B/C mean different things in F, G and J
  (A = v3.5 in F but A = v3.6 in J; C = B + look-around in G); M0/M1/M2 in H. v3.6 is never defined in one place (it is
  "B + look-around" only by inference from Sec. VI-C). Eq. 1 does not contain the crops that define $p_h$ in v3.6, and
  $\max_k p_{h,k}$ is redundant since $p_{h,1}=p_{h,2}$.
- Length is 13 pages: about 10.3 body, 0.7 appendix, 1.7 references (76 entries). See 4 for the cut plan.

### N4. The "Jev" two-model claim
- Clef-Flash is post-trained from Qwen3.5-9B (l.237-239, acknowledged). The pair actually run on one GPU is Clef-Flash +
  Qwen3.5-4B, i.e. two descendants or siblings of the same pretraining run. "Two differently trained AIs" in the abstract
  (l.45) and "diverse redundancy" in Related Work overstate it. Knight and Leveson (cited) is the argument against it.
- The data you already have shows the correlation. On the development set (Table i13dev), Qwen B misses 17 fires and
  the two-model "both approve" rule misses 15, so Clef-Flash also misses at least 15 of Qwen's 17 (88%). The gain from the second
  model is 2 fewer false approvals for 7 fewer correct approvals (357 to 350). This is a diversity result, and it is negative;
  report it as the conditional miss rate $P(\text{Clef misses}\mid\text{Qwen misses})$ with a CI and the Jaccard overlap.
  On T2 no such analysis is possible because both make 0/407 false approvals, so T2 neither supports nor refutes diversity.
- Clef-Flash *alone* (0/407, 187/193, one pass, 0.6 s versus 3.4 s) matches or beats the pair. The paper itself says it "stands out"
  (l.443). So the economics of the two-model design are not argued: why run two models? Add a Clef-only arm to J if the
  GPU time allows (exploratory, labelled).
- J is confounded: J uses Qwen3.5-4B with h35 prompts and no crops, A uses Qwen3.5-9B with h36 + tiles. A difference between J and A cannot be attributed to
  "the second model". The P2 endpoint "unsafe J $\le$ A" will be satisfied by 0 $\le$ 0 on 24 worlds with about 10 fire worlds; that is
  absence of evidence (0/24 has a Wilson upper bound of about 14%). The claim "no extra risk" (l.550) must be "feasible within
  X GB; no unsafe delivery observed in 24 worlds (upper bound 14%)".
- "Jev" is an internal name that is never explained to a reader (it appears 10 times, including in the abstract). Provenance rests
  on a company blog and a Japanese news article (`chen2026clefblog`, `gihyo2026clef`); cite the model card and the licence.
- Fix: demote the section to an "extension" or to the supplement, rename it "second-model veto", and put the correlation
  analysis in. Do not use it in the title.

### N5. Closed-loop headline numbers read stronger than they are
- E (60/60, 0 wrong) was run with v3.5, which in F delivered despite a small fire in 12 of 13 paired worlds (l.463). E's 12 fire trials are
  clearly visible fires. The abstract puts "60/60 with 0 wrong deliveries" before the sentence on the remaining gap, but never states that
  v3.5 fails on small fires 12/13. Add that number next to the 60/60.
- G: the denominator (16 of 24) is the worlds in which the fire is perceivable from at least one of the front or side views, by
  mask render. The comparison B vs C therefore conditions on a label that uses the side views, which only C has. The result
  is true and useful, but the unconditional rate on all 24 worlds should be given too (13/24 vs 23/24 correct is already
  in the macros), and the sentence "this reduced deliveries" should say "among worlds where a side view can see the fire".
- G "median mission time rose from 102 to 122 s" (+20 s). Sec. III-B says "about 30 s per delivery" (l.226) and the Discussion says "about 15 s per side view".
  Make these one measured number.
- B0 = 40 remains definitional. Either remove it from the abstract or say "counterfactual".
- "Six of B's seven misses ... overlap those of fire-free views" (l.465-467). Dev fire-free max was $p_h=0.0007$ (l.582), and the misses are at 0.002-0.006,
  above it. The claim "no threshold can separate them" needs the fire-free distribution of those same worlds (or the sentence
  must go).

### N6. Pre-registration credibility, now at study level
- 12 registrations and all their results fall on 2026-10-16/17 (Table prereg). Registrations are Markdown in the authors' repo.
  Ancestor-in-git is checkable but not independent: history can be rewritten and commit dates are author-controlled. Mirror to
  OSF or Zenodo with timestamps, or cite GitHub push times, before submission.
- The studies are **chained**: F was designed after seeing T1/T2, G after F, H after G (uses G's rates), P2 after P. Each is
  registered, but the sequence of what to register next was driven by results. That is a legitimate exploratory pipeline;
  the text should say "confirmatory within study, sequential across studies" and not use "pre-registered" as a single badge for the whole.
- Post hoc elements that need the label in the text: the 10 000 px cut, the 614/20 px thresholds, the choice of $\tauh=0.05$ after
  a pilot failure, T1 Amendment 3, DH2 added after intermediate DH results, the remark on everyday scenes in P, the
  statement that T2 "happened to be easy".
- Item 3 in "What pre-registration bought us" (l.602-608) lists "any measurable change on T2" as a failed registered claim. T2's registered P1 was
  underpowered; it did not fail. Reword.

### N7. Smaller methodological issues
- Study Z: thresholds were chosen by "fewest development false approvals first". That rule drives CLIP to refuse nearly everything (2/191 correct). It is a
  legitimate registered rule, but then the conclusion "contrastive scores do not separate the classes" is too strong. Also CLIP's processor centre-crops to 224 px
  and cuts off fire at the edges (noted in the registration amendment, not in the paper). SigLIP at 10.8% false approvals with 100% correct approvals shows a different
  operating point is available; give the ROC or a matched-recall comparison. Add one non-contrastive baseline (a mask-trained
  fire segmenter or an open-vocabulary detector).
- R: `tab_r` is TBD; check that clean-reference false approvals are shown per condition, and that the Holm family is stated.
- H P1 uses 8 pairs; the minimum exact two-sided Wilcoxon p is 0.0078, fine, but the 8 pairs come from 8 sequences, and each arm
  carries its own memory trajectory, so M2's mission-3 memory depends on its own mission-2 perception. State this.
- Hazard probability in the paper is "Yes/No next-token probability" from an uncalibrated VLM. Study P shows the scale shifts by 1-2 orders of magnitude
  between renders and real photos. A threshold such as 0.05 is not a probability in any calibrated sense; say "score".

---

## 3. Text-level issues

### 3.1 Overclaims
| Line | Text | Issue |
|---|---|---|
| 22-24, 41 | "approves only if both questions agree with sufficient confidence"; "We prove ..." | The confidence threshold is shown to do nothing (Table ablation A4). The proof is one line (N1). |
| 36-38 | "this reduced deliveries ... with no false stops" | 0/8 false stops per arm is weak; conditional denominator (N5). |
| 44-45 | "the check stayed fail-closed" (R) | Presupposes the R outcome; pooled FA of the degraded check is a pre-registered claim with a bound that may exceed 2%. Also trivial if gate rejection counts as refusal. |
| 45-46 | "original design of two differently trained AIs"; "runs on the robot" | Shared lineage (N4); simulated robot. |
| 53 | "A robot that delivers whatever its inventory says ... will drive into a fire" | Motivation, not a measured fact; fine, but the inventory never mentions fire. |
| 55-56 | "VLMs can now recognise such situations zero-shot, and recent work uses them to detect and explain robot failures [REFLECT, AHA, Du, Sentinel]" | AHA and Du fine-tune; Sentinel monitors policies. "Zero-shot" does not hold for the cited works. |
| 63-64, 132-133 | "acting on unaudited stale memory can be worse than having no memory [Sun & Zhang]" | One 2026 arXiv preprint about spatial memory in navigation, used as the only anchor for H. Check that its finding is "worse than no memory" and not "degrades". |
| 387 | `\TLargeDet` 68/69 and `\TSmallDet` 1/7 | These add to 69/76 = the v3.5 recall, but the paragraph is about the registered v3.4 rule (67/76, `\THazRecall`). Say which rule. |
| 546 | "0/407 (185/193 correct)" hard-coded | Not a macro; `\TTSelCA` is 184/193 for "the selected two-model configuration". Two different two-model configurations are in play; name them and generate both from files. |
| 599 | "The largest single safety gain ... came from moving 0.4 m, not from ... a second model" | Fair for G vs F, but T2 and J cannot discriminate between models (0 vs 0). Say "in our tests". |
| 602-608 | "Three registered claims failed" | One was a power failure (N6). |
| 611 | "roughly 60 s of driving" | Table timing: station 14.3 s + shelter 24.8 s = 39 s. |
| 226 vs 611 vs G | "30 s" vs "15 s per side" vs +20 s measured | Inconsistent (N5). |

### 3.2 Presupposed outcomes (H, J, R still TBD)
Only one `% CHECK-AFTER-H` comment exists (l.525). These sentences also presuppose results and should be reworded as
neutral or conditioned on the macros:
- Abstract l.41-44: "verified memory shortened missions ... while a naive memory ... made X unsafe deliveries against Y" and l.44-46 "stayed fail-closed",
  "runs on the robot on one GPU". Use `\HHeadline`, `\RPoolSupported`, `\JClaim`-style macros or the two variants in section 5.
- l.524-529: "M1 was faster still because it skipped checks" (M1 may not be faster if it fails or refuses); "It also made `\HFalseRefone` false refusals by avoiding stations whose fire was already out"; "Its failures were the ones staleness predicts".
- l.534-537 (Fig. hrate caption): "Naive memory is fast but its risk grows ... Verified memory keeps the risk of the memory-free check and is faster whenever the world is persistent". The model is built from measured rates, so the last clause may fail if P1 fails.
- l.589-597 (Discussion): "Campaign H ... show why this is dangerous", "What memory then buys is efficiency in persistent worlds".
- l.490-496 (R): "The cost is availability. Correct approvals fell ...", "In short, degradation turned errors into refusals rather than unsafe approvals"; Fig. rex caption: "Over-exposure washes out the flames, and the acquisition gate rejects the most extreme frames".
- l.545-551 (J): "Together with Qwen3.5-4B ... it made 0/407" is T2 offline and fine; "the median check latency was `\JLatJ` against `\JLatA`" implies J is slower or faster; keep neutral.
- Intro l.77-80, 91-92: "test it ... against a naive memory that trusts what it saw" is fine; "include a camera-degradation study that probes part of the gap" is fine.
- Conclusion: "A local VLM can serve as a fail-closed gate" must hold even if R fails the 2% bound; condition it.
- `tab_h_arms.tex` and `tab_r.tex` are `\TBD` tables; make `paper_numbers.py` fail the build if a macro is TBD in a final build.

### 3.3 Undefined or unclear terms
"Jev" (abstract, 10 uses); "Clef-Flash" (what is it in one sentence); "v3.6", "configuration B", "tiles/h36", "h35"; "perceivable" vs "visible" fire
(both used, defined by the 614 px mask rule only in Methods); "expected behaviour" (defined per stratum by authors, not in the abstract); "decision model"; "safe delivery"; "campaign" vs "study" (Table lists both); "DH, DH2" (development sets not described in the main text);
"SystemOne API"; "pooled false approvals". Eq. 1: $\max_k p_{h,k}$ vs $p_{h,1}=p_{h,2}$; "four scored queries" vs Eq. 1 (two MC + one hazard). The prompts for the two MC questions are not
shown; the hazard prompt is. "Eleven studies" (l.91) vs Table audit's 12 rows and the "two closed-loop campaigns" in l.88-89 (outdated; there are
D, E, F, G, H, J).

### 3.4 Citation spot-check against `references.bib` (8 of 76)
1. **agia2025sentinel** (Intro, l.56): cited as a VLM that "detects and explains robot failures". The bib title is "Unpacking Failure Modes of Generative Policies: Runtime Monitoring of Consistency and Progress", a policy monitor. Weak fit for the sentence; fine in Related Work.
2. **du2023successdetectors** (l.56 and l.101): "fine-tune a VLM as a success detector". Title matches; but the Intro sentence says zero-shot. Split the sentence.
3. **sun2026memorylies** (l.63, 133): arXiv-only; spatial memory staleness in navigation agents, used as general evidence on stale supply memory. Verify the "worse than no memory" claim; otherwise soften.
4. **angelopoulos2021conformal** (l.107): a tutorial cited for "KnowNo's conformal guarantee". Acceptable as background; the original guarantee is Vovk et al. split conformal prediction, and KnowNo's own theorem.
5. **hofman2023preregistration** (l.89): "Pre-registration for Predictive Modeling" is about ML evaluation; it supports the practice but not the "registered simulation campaign" use. Fine as a secondary citation; Nosek 2018 is the primary one.
6. **chen2026clefblog / gihyo2026clef** (l.236): a corporate blog and a Japanese news article for model provenance. Cite the Hugging Face model card and the licence; drop the news article.
7. **venancio2022dfire** (l.500): correct paper title for D-Fire, but data were taken from a Hugging Face mirror (`badsaarow/d-fire`). "Public domain (CC0)" for scraped web photographs is doubtful; check the licence at the original repository and say "as tagged on the mirror" until then.
8. **yuan2026whentoact** (l.104): bib note says "to appear; proceedings entry not independently checked". Either check or cite the arXiv version. Also **hofer2021sim2real** is a three-page editorial; "a central obstacle" is better supported by a survey (e.g. Zhao et al.).
Relevant and fine: kadavath2022know, zhao2021calibrate, hendrycks2019benchmarking, ravichandran2026guardrails, robinson2023mcqa.
Related-work gaps from round 1 still open: Whitehead et al. 2022 (reliable VQA with abstention) and Elhafsi et al. 2023 (semantic anomalies) are in neither the bib nor the text; Liang et al. 2024 (introspective planning) is in the bib.

### 3.5 Numbers across abstract, body and tables
- Abstract mixes system versions: T1 numbers are v3.4 ("registered system", 5/408), E is v3.5, F/G/H/J/R are v3.6. Add a footnote or a six-row table with version, study, endpoint.
- Abstract "an item swapped / empty": E is the only study where all three failure types are tested; F/G/H/J are fire-heavy.
- Table E sums: 12+4+2+... = 60; ETaskSuccess 36 = allow 20 + after search 16. Consistent.
- G: 11 to 1 of 16 gives exact McNemar p = 2/1024 = 0.0019 only if all 10 discordant pairs go one way. Report the discordant counts; F: 12 to 7 of 13 gives p = 0.0625 for the same reason. Say "5 of 5 discordant".
- Abstract "unseen lighting, object placement and distractors" (round 1) is now accurate and the T1 description is better; still no real OOD.

---

## 4. Cut plan to 8 pages of body + references

Current: about 10.3 pages body, 0.7 appendix, 1.7 references (76 entries). Target: 7-8 pages body, about 1.3 pages of references (about 50 entries). Estimated savings in page units:

| Item | Action | Saves |
|---|---|---|
| Failure analysis (l.560-590) | Keep wheel-axis frame and the threshold pilot (0.3 page); rest (QoS, DDS, latch, loader secure mode, generator bug) to supplement | 0.7 |
| Related Work | Cut from 1.3 to 0.6 page: merge safety/active perception/robustness/redundancy/evaluation into 3 paragraphs; remove scene-graph and mapping lists | 0.7 (and 20+ refs) |
| Fig. e_trajectories + Table E strata | Supplement; one sentence + counts in text | 0.5 |
| Table timing | One sentence in text | 0.25 |
| Fig. risk_coverage (flat, uninformative) | Supplement | 0.25 |
| Fig. r_examples (figure*) | Supplement; keep the R table only | 0.35 |
| Algorithm 1 | Supplement or reduce to 5 lines | 0.3 |
| Ablation table (Table II) | Two rows in the text (3B 36 vs 4, 9B unchanged); table to supplement | 0.25 |
| Z table | Three numbers in text | 0.2 |
| Section Jev + its results | Merge to one 0.4-page subsection, demote ("second-model veto") | 0.4 |
| Instruction parsing | Supplement | 0.15 |
| Table I (studies) | Reduce to 4 columns; move audit appendix to supplement | 0.35 |
| Discussion | Cut to Limitations-style 2 paragraphs | 0.2 |
| Appendix A (dev models) | Supplement | 0.35 |
| **Total** | | **about 4.9 pages** |

That reaches about 5.4 pages before additions. Reserve about 1.5 pages for what is missing: the version table (0.15), P2 and ROC on real photos (0.4), the conditional-miss analysis for the two models (0.15), the mission-level memory bound and H break-even figure (0.4), a rendered-image figure (fig_t1_examples is already included; keep), and a short threats paragraph. Result: about 7.5 pages body.

If the venue counts references inside 8 pages, take two further steps: drop J and R-examples entirely from the main text (supplement only) and cut references to about 40.

Structure suggestion: I. Intro (0.7); II. Related (0.6); III. System (check, look-around, memory, guard: 1.6); IV. Evaluation method and registration (0.7); V. Results (T1+Z, E, G/F, R+P/P2, H: 2.6); VI. Limitations and conclusion (0.4). Two-model veto in V as one paragraph. Alternative if still too long: split into (A) check + look-around + real-image/degradation (RA-L) and (B) memory (IROS/ICRA). Memory with the exposure-bound and break-even analysis is a defensible stand-alone short paper; the present version of the Proposition is not.

---

## 5. Recommended title and abstract

**Title.** *Look Again, Remember Safely: A Fail-Closed Vision-Language Gate for Relief-Supply Delivery Robots*
(Drops "Jev", the "two AIs" and "safety-monotone", which a reader cannot parse in a title. If memory is split off: *Memory Proposes, Perception Disposes: Never-Skip Mission Memory for Fail-Closed Delivery Robots*.)

### Abstract (variant A: H, R come in as registered; J dropped from the abstract; macros counted as one word each, under 200)

> Relief inventories cannot be trusted: supplies are swapped, shelves are empty, sites burn. \sys{} is a simulated delivery robot that verifies the item with a local vision-language model (VLM) before carrying it to a shelter. The VLM never writes the decision: it scores answer letters for two permuted multiple-choice questions and a Yes/No hazard question, and the robot approves only if they agree and no fire is seen. An independent guard keeps the VLM from the actuators. On a pre-registered held-out set of \TNimages{} images the check made \TFA{} false approvals in \TNdeny{} must-refuse cases (\TFACI), all partly hidden fires, so the registered 2\% target was missed. Looking from 0.4\,m to either side cut deliveries despite a perceivable fire from \GWrongB{} to \GWrongC{} of \GPairs{} paired worlds (exact McNemar $p=\GMcNemarP$). Mission memory may reorder checks and tighten thresholds but never skip one: in \HPTwoN{} missions it shortened relocated missions by \HTimeDiff\,s ($p=\HPOneP$), while a naive memory made \HUnsafeMone{} unsafe deliveries against \HUnsafeMtwo{}. Under \RNcond{} camera degradations, pooled false approvals were \RPoolFA. On real photographs the hazard question flagged \PRecall{} fire or smoke images but also \PFalseAlarm{} fire-free ones, so site calibration is required. Code and all trial logs are released.

### Variant B: results not as registered (swap these sentences)
- Memory: "…in \HPTwoN{} missions in changing worlds verified memory was not significantly faster ($p=\HPOneP$) / naive memory made no more unsafe deliveries than verified memory ($p=\HPTwoP$); we report the per-story outcomes and the break-even change rate."
- R: "Under \RNcond{} camera degradations pooled false approvals were \RPoolFA, above the registered bound, driven by \RWorstCond." (Use `\RPoolSupported` only inside the body, not as a macro in the abstract sentence.)
- Two-model veto (only if kept in the abstract): "A second, post-trained decision model shared a GPU with the first but did not reduce unsafe deliveries; their fire misses overlapped (X of Y)."
- Never add: "stayed fail-closed", "no extra risk", "differently trained".

Both variants: state the E headline with its caveat in the body ("60/60 with 0 wrong deliveries on full-size fires; the same system delivered despite a small fire in 12 of 13 paired worlds").

---

## 6. Fair credit (keep and lead with these)
- Negative results reported (T1 target missed, T2 uninformative, F not significant).
- Mask-based labels and ground-truth audit; the wheel-axis finding.
- G is a clean, paired, adequately powered test of a sensing fix.
- Registration audit table, seeded specs, numbers generated from files.
- The caveat on Proposition 1 (per check, not per trajectory) in the paper itself.

## 7. Top 5 actions
1. Make memory honest: demote Prop. 1, add the exposure-based mission bound and break-even `q*`, add a fair M1b baseline, relabel the M1-vs-M2 p as "by design" (N1).
2. Put the real-image result in the abstract: P and P2 together, with ROC; reword "fail-closed gate" (N2).
3. Cut to about 8 pages with the table in section 4; unify v3.x/A-B-C names; define v3.6 once (N3).
4. Demote the Jev section, add the conditional-miss analysis, and drop "differently trained" (N4).
5. Neutralise presupposing sentences (3.2), fix the 30/15/20 s and 60 s inconsistencies, and mirror registrations to an external timestamp (N6).
