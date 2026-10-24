# Novelty threat scan, 2026-07-01 to 2026-10-18 (plus gaps in the earlier reviews)

Date of scan: 2026-10-18. Complements `LITERATURE_REVIEW.md` (2026-10-17) and `LITERATURE_I24.md`; items already in `references.bib` are not
repeated here unless the new reading changes their rating.

## 0. Method, and what "verified" means here

* Search: WebSearch (US-only index, about 25 queries on the six topics in the brief) followed by a fetch of the arXiv abstract page (`arxiv.org/abs/ID`) of every
  hit that is rated below. **V-abs** = title, authors and submission date were read on the arXiv abstract page in this session. Where the HTML full text was
  also fetched, the table says **V-text** and names what was read. **U** = known only from a search listing; not rated beyond "low" and not given BibTeX.
* Not read: IEEE/ACM pages, OpenReview, proceedings (nothing in the window had appeared there in the index). Almost every hit is an arXiv preprint without
  a venue. Peer-review status is unknown for all of them; one is stated to be a workshop paper (ICML 2026 AIWILD workshop, 2609.22949).
* Dates are the arXiv v1 submission date as printed on the abstract page. One id does not match its printed date (2609.27816 shows 18 Aug 2026); it is cited as printed.
* Numbers quoted come from the abstract page unless marked V-text.

Our four claimed contributions, as used in the threat column:

* **C1** Advice may only reorder visits or tighten thresholds; Prop. 2 bounds unsafe delivery by the gate's own budget eps_any; necessity (characterization);
  machine-checked with z3 against a transcription of the code.
* **C2** Look-around side views shrink eps.
* **C3** Advice credit bounds the price of advice over missions.
* **C4** Pre-registered closed-loop studies in Gazebo (ground-truth audited, naive and filter baselines).

## 1. Bottom line

1. **No paper in the window (or earlier, within what the index shows) combines a typed tighten-only advice interface, a bound by the perception gate's own error
   budget, and a ground-truth-audited closed-loop robot evaluation.** The "to our knowledge, new is the combination" sentence still holds, but it now sits
   closer to three neighbours than the current text admits: AuthGuard-R (robot, provenance, formal non-escalation, no perception error), SafeCommit (probabilistic
   bound, poisoned memory, probe actions, no robot) and DelegateGuard/APPA (attenuation-only and monotone labels with proofs, no perception). Details in Sec. 5.
2. **Top threats** (all arXiv preprints, none peer-reviewed as far as we can see):
   1. AuthGuard-R (2609.31110, 25 Sep 2026): C1 medium to high (principle and "mission non-escalation" for LLM robots, memory as an untrusted provenance source).
   2. SafeCommit (2608.04289, 4 Aug 2026): C1 medium, C2 medium (a low-side-effect probe to shrink the set of plausible worlds is the same move as a look-around).
   3. DelegateGuard (2610.16005, 12 Oct 2026) and APPA (2607.24625): C1 medium (attenuation-only capabilities, monotone-descending labels, with a
      proposition on where attenuation suffices; both software agents).
   4. TOWN-VLA (2608.23224, 24 Aug 2026): C1 medium (retrieved text may not change the executed prompt except through a fixed admission rule; physical arm).
   5. "What Can Be Enforced?" (2607.22868, 24 Jul 2026): C1 medium for the word "characterization" (it characterizes exactly which policies a deterministic gate can enforce).
3. **Weakened claims to reword:** "machine-checked" is no longer rare as a word (TLC in TMA-NM, Lean 4 in GIF, SMT in AgentFlow); ours is distinctive because it checks a transcription of the
   deployed gate code and the bound, so say that. Pre-registration: do not say "first" (two LLM-agent studies in 2026 pre-registered, see C4 below); the restriction to
   closed-loop robot safety audits still looks open.
4. **Evidence that supports us (cite):** Semantic DoS (2604.24790) shows the availability price an attacker can buy is real for LLM robots (supports C3 framing);
   the CPV-gate paper (2608.06830) shows peer-robot claims are an attack channel and a filter still leaves 36.6 % violations (supports "guarantee must not depend on recognizing advice as malicious");
   VP-CONTROL (2609.10969) shows an independent evidence source beats a second vote over shared evidence by 40.9 points (supports C2: a side view is an independent source).

## 2. Table of hits

Threat columns: none / low / medium / high. "V-abs" or "V-text" as defined in Sec. 0.

| # | Work | Date, id | Read | One-line summary | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|---|---|---|
| 1 | Chepuri, Srivastava. AuthGuard-R: Safety-Compliant Mission Hijacking and Dual-Gate Defense for LLM-Controlled Robots | 25 Sep 2026, arXiv 2609.31110 | V-text (first 100k chars) | Signed mission token + provenance labels; deterministic authorization gate beside an independent safety gate; theorems incl. mission non-escalation (Lemma IX.2), provenance separation (IX.6), dual-gate trace composition (IX.9); 109/109 injected deviations rejected in a 240-trial LLM-only study (Claude Haiku 4.5, Qwen2.5 7B); simulator/ROS 2 left to future work; memory treated as an untrusted source; safety gate is an abstract predicate, perception error explicitly out of scope | medium-high | none | none | low |
| 2 | Akewar, Ranjan. SafeCommit: Certifying When Memory-Grounded Agents May Safely Act | 4 Aug 2026, 2608.04289 | V-text | Between reasoning and execution: calibrated set of plausible worlds from memory, observations, provenance; commit only if safe in every retained world, else run a low-side-effect probe or fall back; P(unsafe commit) <= alpha, <= alpha + beta with imperfect world proposals; poisoned memory 62.5 % -> 3.9 %; symbolic simulator, no VLM, no robot, no proof assistant; says per-decision bounds do not extend to long missions | medium | medium | low | low |
| 3 | Kravchenko et al. APPA: Recoverable Information-Flow Control for Real-World LLM Agents | 27 Jul 2026 (v2 26 Aug), 2607.24625 | V-abs | Trajectory labels descend monotonically in a finite lattice, pre-dispatch and post-return checks, disposable child branches; claimed proofs; 0 attacks in 1,320 guarded episodes | medium | none | none | low |
| 4 | Tran-Truong et al. DelegateGuard: Purpose-Bound Capabilities for Delegated LLM Agent Workflows | 12 Oct 2026, 2610.16005 | V-abs | Attenuable capabilities (purpose, labels, operations, sinks, depth), mediated outside the LLM, revocation cascades; Prop. 1 states exactly where attenuation-based authorization suffices | medium | none | low | low |
| 5 | Ray. What Can Be Enforced? A Theory of Certified Runtime Safety for Tool-Using Agents | 24 Jul 2026, 2607.22868 | V-abs | Exactly which safety policies a deterministic pre-execution gate can enforce (register model); PSPACE for a monotone fragment (caps, revocation); Neyman-Pearson false-block/miss trade-off; conformal finite-sample certificate; closed-loop effects of blocking | medium (necessity/characterization wording) | low | low | low |
| 6 | Zhou et al. TOWN-VLA: Think Only When Needed: Prompt-Authority Control for Selective Slow-Path Intervention in VLA Manipulation | 24 Aug 2026, 2608.23224 | V-abs | Retrieved text acts as a control input: raw append cut success 92.5 % -> 3.0 %; interface separates candidate text from permission to change the policy input, fixed rule admits a canonical instruction or restores the base prompt (900/900 routes); physical PiPER arm, 52.7 % -> 78.7 % | medium | none | none | low |
| 7 | Huang et al. When Coordination Becomes a Threat: Communication Attacks in LLM-Controlled Multi-Robot Systems | 7 Aug 2026, 2608.06830 | V-abs | Peer-message attacks on three multi-robot architectures (up to 100 % activation); Claim Provenance and Verification gate cuts violations 70.0 % -> 36.6 %, no guarantee | low (supports) | none | low | low |
| 8 | Steinberg, Gal. Semantic Denial of Service in LLM-controlled robots | 25 Apr 2026, 2604.24790 | V-abs | Short safety-sounding injected phrases make the robot halt; prompt-only defenses trade attack suppression against hazard response; fix is architectural | low (supports) | none | low (supports availability price) | none |
| 9 | Palumbo et al. Formal Policy Enforcement for Agentic Systems (v1 18 Feb 2026, v4 12 Oct 2026) | 2602.16708 | V-abs | Datalog policies, event-graph runtime monitor, blocks a tool call that would violate the policy given history | low-medium | none | none | none |
| 10 | Shivakumar et al. AgentFlow: A Flow-Centric Policy Language and Framework for Securing LLM Agent Systems | 24 Aug 2026, 2608.22868 | V-abs | Labeled-edge flow policies, task-scoped capabilities, bounded SMT verification of 7 properties of the policy fragment; AgentDojo compromise 33.0 % -> 0.0 % | low-medium | none | none | none |
| 11 | Storek et al. GIF: Locally Sound Geometric Information Flow Control for LLMs | 22 Jun 2026, 2606.23277 | V-abs | Jacobian-based upper bound on information flow from untrusted spans; mechanized Lean 4 proof of local soundness | low | none | none | none |
| 12 | Santos-Grueiro. Context-to-Execution Integrity for LLM Agents | 7 Jul 2026, 2607.06000 | V-abs | Deterministic gate admits a call only if field, effect and invocation authority bind to one action manifest; typed releases; AgentDojo 720 episodes | low-medium | none | none | none |
| 13 | Louck. TMA-NM (already in bib as `louck2026tma`) | 23 Jun 2026, 2606.24322 | V-text | Re-read: "machine-checked" = TLA+ models checked by TLC on a bounded model (3 slots, 2 sessions, k=2) plus an inductive invariant; cross-agent shared memory is explicitly out of scope; vision-derived memory "simply untrusted unless elevated"; no robots | medium (memory) | none | none | none |
| 14 | Wu et al. From Intent to Execution Grant: An Execution-Boundary Conformance Profile for High-Risk AI Actions (EBL-Core) | 10 Sep 2026, 2609.11596 | V-abs | Specification of "policy non-weakening", evidence obligations, deterministic adjudication, grants; 34 test vectors; explicitly not mechanized | low-medium | none | none | none |
| 15 | Zheng et al. Engineering Reliable Commit Gates for Agentic AI (VP-CONTROL) | 10 Sep 2026, 2609.10969 | V-abs | Verifier diversity vs evidence-source diversity: shared-evidence vote approves 62.9 % of unsafe proposals vs 22.9 % with an independent source; 1.9 % unsafe at 5 % per-task target; a preregistered live study | low | low (supports: independent evidence) | none | low-medium (a pre-registered live study exists, but software) |
| 16 | Williams et al. Predicting LLM Safety Before Release by Simulating Deployment | 8 Jul 2026, 2607.07184 | V-abs | Predictions for GPT-5.4 pre-registered and outcome-blinded; other three releases retrospective | none | none | none | low-medium (prior pre-registered prediction-then-test, not robotics) |
| 17 | Dwedar et al. Safe Multi-Robot Coordination via VLM-LLM Reasoning and Reachability Analysis | 18 Aug 2026 (printed), 2609.27816 | V-abs | LLM advises task allocation, VLM output becomes conservative constraints, a zonotope reachability gate holds command authority; "strict separation between advisory reasoning and verified execution" | low-medium | none | none | none |
| 18 | Lu et al. CertVLA: Certified Defense against Physical Visual Attacks for VLA Models | 21 Aug 2026, 2608.20791 | V-abs | Covering masks + calibrated disagreement give a closed-loop certificate against bounded patch attacks | low (certifies a different thing) | none | none | none |
| 19 | Qin et al. Harnessing Embodied Agents: Runtime Governance for Policy-Constrained Execution | 9 Apr 2026 (v4 10 Jun), 2604.07833 | V-abs | Governance layer (admission, monitoring, rollback); 96.2 % interception in 1,000 simulated trials | low | none | none | low |
| 20 | Singh. When Does Belief-Based Agent Memory Help? | 20 Jun 2026, 2606.22030 | V-abs | Provenance-capped updating bounds trust by source; resists volumetric poisoning at a utility cost | low | none | none | none |
| 21 | Nakayashiki. When Stale Constraints Go Unchecked | 26 Aug 2026, 2608.25553 | V-abs | Agents seldom re-verify a settled constraint (77 % stale-consistent decisions); verification-slot reallocation fixes most | low (supports the memory-verification motivation) | none | none | none |
| 22 | Sima et al. Self-Evolving Just-In-Time Memory for Proactive Embodied Safety | 26 Jun 2026, 2607.16247 | V-abs | Belief graph + factual memory + experience memory for hazard anticipation (IS-Bench) | low | none | none | none |
| 23 | Wen et al. INSPECT: Learning Robot View Selection from Assistant Use | 17 Sep 2026, 2609.20615 | V-abs | Learned view selection for verifiability of assembly parts; human-rated verifiability 34.8 % -> 41.7 % | none | low | none | none |
| 24 | Winston et al. Solver-Aided Verification of Policy Compliance in Tool-Augmented LLM Agents | 20 Mar 2026, 2603.20449 | V-abs | NL policies to SMT, Z3 checks planned tool calls pre-execution | low (z3 gate, not code-transcription proof) | none | none | none |
| 25 | Wu et al. Provably Secure Agent Guardrail | 28 May 2026, 2605.29251 | V-abs | Proof-constrained action: agents state first-order constraints, solver checks; 0 % attack success in 2D simulations | low | none | none | none |
| 26 | Nguyen et al. VEPA: Verified Evolving Formal Policy for Lifelong LLM Agent Guardrails | 8 Oct 2026, 2610.12813 | V-abs | LLM proposes policy patches, deterministic verifier accepts; a rule activates only with enough evidence so uncertain updates cannot change decisions | low | none | none | none |
| 27 | Yu et al. NOMOS: Compiling Written Policies into Statically Verified Tool-Call Gates | 8 Oct 2026, 2610.11030 | V-abs | Policy compiler to deterministic gate; AgentDojo banking ASR 0 % | low | none | none | none |
| 28 | Huang et al. Trust in LLM-controlled Robotics: a Survey | submitted 17 Dec 2025, 2601.02377 | V-abs | Survey; categories include formal safety specification, runtime enforcement, multi-LLM oversight, prompt hardening | none (context) | none | none | none |
| 29 | Yeke et al. RoboJailBench | 19 May 2026, 2605.19328 | V-abs | Benchmark of jailbreak attacks and two defenses on embodied VLMs | none | none | none | low |
| 30 | Liu, Yan. VULCAN (fire-disaster multi-agent VLM navigation) | 14 Apr 2026, 2604.12831 | V-abs | Habitat benchmark with smoke and heat; failure modes of baselines | none | none | none | none |
| 31 | Agarwal, Raghunathan. Multi-Link Safety Filtering for VLA Policies Around Moving Hazards | 30 Sep 2026, 2609.40007 | V-abs | Training-free barrier shield for VLA arm links | none | none | none | none |
| 32 | Yin, Zhang. VLAGuard | 2 Aug 2026, 2608.01028 | V-abs | Attention-hijack patches on VLA; fine-tuning defense | none | none | none | none |
| 33 | Paul, Nandy. Beyond Single-Model Injection (multi-agent) | 19 Sep 2026, 2609.22949 | V-abs | Threat model and four architectural defenses, ICML 2026 AIWILD workshop | low | none | none | none |

Listed but **not read beyond a search listing (U)**, not rated above low and not given BibTeX: SoK on foundation-model robots (2606.16788), world-model embodied security
survey (2607.28226), embodied-AI safety survey (2605.02900), ShieldVLA (2609.13231), SafeVLA-Bench (2606.00773), HBEE pre-registered LLM simulation (2605.07472),
OpenETA (2608.03924, "preregistered seeds" per a snippet), DelegateGuard-adjacent delegation papers (2609.00267, 2605.05440), GoalBelief GitHub issues
(ll7/robot_sf_ll7 #8084, #8085: a planned pre-registered closed-loop pedestrian-prediction benchmark, not a publication, parked on 12 Oct 2026).
Already in `references.bib` and not rescored: `samarakoon2026paper` (2608.05715), `liu2026embodiedsecurity` (2608.16843), `nagaraja2026prompts` (2608.00747),
`dorzhiev2026ripa` (2606.28649), `obi2026safegate` (2604.05427), `oloo2026vaptamp` (2604.26988), `sun2026memorylies`/2608.04574.

## 3. Per-contribution assessment

**C1 (tighten-only advice, bound by eps_any, characterization, z3).**
The principle is now stated in four more places: AuthGuard-R (non-escalation for robots), DelegateGuard (attenuation-only), APPA (monotone label descent), TOWN-VLA
(admission rule over retrieved text). What none of them has is the other half of our claim: a bound whose right-hand side is the error of a *perceptual* check
(AuthGuard-R says perception errors "must be measured separately"; its safety gate is an abstract predicate; DelegateGuard and APPA have no stochastic component;
SafeCommit has a stochastic bound but its randomness is calibration of a world model, not a VLM at the station). The z3 claim is safe if phrased exactly: against a
*transcription of the deployed gate code*, not a policy model (TMA-NM: TLC on a bounded model; GIF: Lean on a local-soundness statement; AgentFlow and Solver-Aided: SMT on policies).
"Necessity (characterization)": DelegateGuard's Prop. 1 ("exactly where attenuation suffices") and "What Can Be Enforced?" (exactly which policies a gate can enforce)
are characterizations in the same genre; ours is about which advice types can be admitted without exceeding the budget. A reviewer may ask for a one-sentence comparison.

**C2 (look-around shrinks eps).** No new paper tests a revoke-only second view for hazard detection. Closest: SafeCommit probes (software, no perception), VAP-TAMP (already cited), INSPECT (learned
view selection, assembly). VP-CONTROL's independent-evidence result is useful support. Threat low.

**C3 (advice credit).** No new paper bounds the price of advice over missions. Semantic DoS gives motivation (an injected phrase buys a halt). The learning-augmented line was already covered; searches for
"LLM agent + consistency/robustness" returned nothing relevant. SafeCommit states per-decision bounds do not extend to long-horizon missions, which is the gap C3 fills. Threat low.

**C4 (pre-registered closed-loop studies).** Pre-registration now appears in LLM safety work: 2607.07184 (outcome-blinded prediction for GPT-5.4) and VP-CONTROL (a preregistered live study). No pre-registered
closed-loop *robot* safety audit was found; HRI reviews report low uptake (3.4 % of 296 child-robot-interaction papers, from the 2023 review `spitale2023reproducibility` already cited). Do not write "first"; write "we found no".

## 4. Suggested sentences for the related-work section (LaTeX)

Keys marked (new) are defined in Sec. 6. Insert in the paragraph "Untrusted inputs to embodied agents", after the sentence ending "(RoboGuard~\cite{ravichandran2026guardrails})".

**4.1 AuthGuard-R, communication attacks, semantic DoS (highest priority).**

```latex
Concurrent work binds robot actions to a signed mission and input provenance and proves that an LLM planner cannot enlarge the authorized action set (AuthGuard-R~\cite{chepuri2026authguardr}); it leaves perception errors outside the proof, and its evidence is a planner-only study without a simulator.
Peer messages are an attack channel in LLM-controlled multi-robot teams, and a claim-verification filter lowers but does not remove violations (36.6\,\% remain)~\cite{huang2026coordination}; injected safety-sounding phrases can also buy a halt~\cite{steinberg2026semanticdos}, the availability price that our advice credit bounds.
```

**4.2 Monotone and attenuation-only authority for software agents.**

```latex
Attenuation-only capabilities and monotonically descending integrity labels with proofs exist for tool-using software agents~\cite{trantruong2026delegateguard,kravchenko2026appa,palumbo2026formalpolicy}, and a recent theory characterizes which safety policies a deterministic gate can enforce~\cite{ray2026whatenforced}; none has a stochastic perceptual check whose error budget is the right-hand side of the bound.
For retrieved text that would enter a VLA prompt, TOWN-VLA admits only a fixed canonical instruction or restores the base prompt~\cite{zhou2026townvla}; our interface applies the same one-way rule to visit order and thresholds at a pre-action gate and bounds the unsafe-delivery probability.
```

**4.3 SafeCommit (memory plus probabilistic certificate).**

```latex
SafeCommit~\cite{akewar2026safecommit} releases a side-effecting action only if it is safe in every world still plausible given memory and observations, and runs a low-side-effect probe otherwise, with P(unsafe commit)$\le\alpha+\beta$ per decision on a symbolic simulator; we differ in a VLM gate whose own error is the budget, a typed advice interface that can only reorder or tighten, a bound over missions, and closed-loop audits against ground truth.
```

**4.4 Memory poisoning scope.**

```latex
TMA-NM proves, with TLC on a bounded model, that origin-bound authority resists memory poisoning, and places cross-agent memory out of scope~\cite{louck2026tma}; peer reports are exactly what our typed advice covers.
```

**4.5 Machine-checking wording (Sec. on the formal part).**

```latex
Machine-checked guarantees for agent gates usually verify a policy model (TLC~\cite{louck2026tma}, Lean for an information-flow bound~\cite{storek2026gif}, SMT for flow policies~\cite{shivakumar2026agentflow,winston2026solveraided}); we check the bound against a transcription of the deployed gate code.
```
(Only keep this if the z3 check really covers the transcribed gate; the sentence is accurate only for that case.)

**4.6 Pre-registration.**

```latex
Pre-registered predictions and live studies have begun to appear in LLM-agent safety work~\cite{williams2026simulatingdeployment,zheng2026commitgates}; we found no pre-registered closed-loop robot safety audit.
```

**4.7 Independent evidence for look-around (optional).**

```latex
Verifiers that share the proposer's evidence approve many unsafe proposals (62.9\,\% versus 22.9\,\% with an independent evidence source)~\cite{zheng2026commitgates}, which is why our side views are fresh observations and not further votes on the front view.
```

## 5. Verdict on the "to our knowledge, new is the combination" sentence

Current text (`main.tex`, Related Work): "What is new, to our knowledge, is the combination of three elements: a probabilistic perception gate on a simulated mobile robot, a bound relative to the check's
own error with a measured availability cost, and a ground-truth-audited comparison with naive and filter baselines (registered, study A)."

**It still holds** for 2026-10-18 against everything found: AuthGuard-R has the robot and the formal non-escalation but no perception error and no evaluation in simulation; SafeCommit has a probabilistic bound and
memory poisoning but no robot, VLM or ground-truth audit; DelegateGuard, APPA, TOWN-VLA have attenuation or admission rules without a perceptual error budget; CPV gate and Semantic DoS are attack/filter studies.
**Recommended edits so it keeps holding:**

1. Add "as of October 2026" and name the nearest neighbours in the sentence before it (4.1 to 4.3), so a reviewer sees we know them.
2. Keep "perception gate" and "bound relative to the check's own error" in the sentence: these are exactly what the neighbours lack. Avoid "first" and avoid stating the tighten-only rule as new (it is attenuation/monotone labels; the paper already says so).
3. Check the claim "memory and peers as typed advice" against TMA-NM (single-agent memory only) and CPV (peer claims, filter): wording "to our knowledge, not bounded by a gate's error budget" is safe; "not typed" is not.
4. If the z3 check is described, say it is against the gate code, as in 4.5.
5. Residual risk: the field is moving about monthly (six relevant preprints in the last 10 weeks). Posting the preprint before camera-ready would timestamp C1 and C3.

## 6. BibTeX (new keys only)

All entries: V-abs (arXiv abstract page read 2026-10-18) unless a comment says otherwise. Format follows the existing `@misc` entries in `references.bib`. The key `nguyen2026vepa` avoids
the existing `nguyen2026openbelief`; `wu2026provably` and `wu2026ebl` avoid `wu2025abstaineqa`. No `howpublished`/`url` fields are given because the existing entries use `eprint`.

```bibtex
@misc{chepuri2026authguardr,
  author        = {Chepuri, Saidattu and Srivastava, Vikas},
  title         = {{AuthGuard-R}: Safety-Compliant Mission Hijacking and Dual-Gate Defense for {LLM}-Controlled Robots},
  year          = {2026},
  eprint        = {2609.31110},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 25 September 2026}
}

@misc{akewar2026safecommit,
  author        = {Akewar, Mayur and Ranjan, Ravi},
  title         = {{SafeCommit}: Certifying When Memory-Grounded Agents May Safely Act},
  year          = {2026},
  eprint        = {2608.04289},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 4 August 2026}
}

@misc{kravchenko2026appa,
  author        = {Kravchenko, Arseny and Liventsev, Vadim and Konstantinov, Innokentii and Iskhakov, Ildar and Kukuy, Matvey},
  title         = {{APPA}: Recoverable Information-Flow Control for Real-World {LLM} Agents},
  year          = {2026},
  eprint        = {2607.24625},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 27 July 2026 (v2 26 August 2026)}
}

@misc{trantruong2026delegateguard,
  author        = {Tran-Truong, Phat T. and Vo, Ha and Tran, Nhut and Vo, Khang and Truong, Thai-Minh},
  title         = {{DelegateGuard}: Purpose-Bound Capabilities for Delegated {LLM} Agent Workflows},
  year          = {2026},
  eprint        = {2610.16005},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 12 October 2026}
}

@misc{ray2026whatenforced,
  author        = {Ray, Shawn},
  title         = {What Can Be Enforced? {A} Theory of Certified Runtime Safety for Tool-Using Agents},
  year          = {2026},
  eprint        = {2607.22868},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 24 July 2026}
}

@misc{zhou2026townvla,
  author        = {Zhou, Zhiruo and Li, Zelin and Chen, Xiwen and Li, Jiazhuo and Wang, Chenwei and Chen, Huiming and Zhu, Xiaojun},
  title         = {Think Only When Needed: Prompt-Authority Control for Selective Slow-Path Intervention in Vision-Language-Action Manipulation},
  year          = {2026},
  eprint        = {2608.23224},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 24 August 2026; method name TOWN-VLA}
}

@misc{huang2026coordination,
  author        = {Huang, Zhen and Liu, Zhihuang and Shi, Weijia and Yang, Yifan and Wu, Weishang and Cai, Zhiping},
  title         = {When Coordination Becomes a Threat: Communication Attacks in {LLM}-Controlled Multi-Robot Systems},
  year          = {2026},
  eprint        = {2608.06830},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 7 August 2026}
}

@misc{steinberg2026semanticdos,
  author        = {Steinberg, Jonathan and Gal, Oren},
  title         = {Semantic Denial of Service in {LLM}-controlled robots},
  year          = {2026},
  eprint        = {2604.24790},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 25 April 2026}
}

@misc{palumbo2026formalpolicy,
  author        = {Palumbo, Nils and Choudhary, Sarthak and Choi, Jihye and Amir, Guy and Chalasani, Prasad and Dillig, Isil and Jha, Somesh},
  title         = {Formal Policy Enforcement for Agentic Systems},
  year          = {2026},
  eprint        = {2602.16708},
  archivePrefix = {arXiv},
  note          = {Preprint, v1 18 February 2026, v4 12 October 2026; v1 title read "Formal Policy Enforcement for Real-World Agentic Systems" in a search listing}
}

@misc{shivakumar2026agentflow,
  author        = {Shivakumar, Basavesh Ammanaghatta and Priya, Swarn and Gao, Peng},
  title         = {{AgentFlow}: A Flow-Centric Policy Language and Framework for Securing {LLM} Agent Systems},
  year          = {2026},
  eprint        = {2608.22868},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 24 August 2026}
}

@misc{storek2026gif,
  author        = {Storek, Adam and Holzer, Nikolaus and Zhang, Zhuo and Jana, Suman},
  title         = {{GIF}: Locally Sound Geometric Information Flow Control for {LLMs}},
  year          = {2026},
  eprint        = {2606.23277},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 22 June 2026}
}

@misc{santosgrueiro2026cxi,
  author        = {Santos-Grueiro, Igor},
  title         = {Context-to-Execution Integrity for {LLM} Agents},
  year          = {2026},
  eprint        = {2607.06000},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 7 July 2026}
}

@misc{winston2026solveraided,
  author        = {Winston, Cailin and Winston, Claris and Just, Ren{\'e}},
  title         = {Solver-Aided Verification of Policy Compliance in Tool-Augmented {LLM} Agents},
  year          = {2026},
  eprint        = {2603.20449},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 20 March 2026}
}

@misc{zheng2026commitgates,
  author        = {Zheng, Zihao and Li, Baichuan and Yao, Junyi and Long, Jiayu},
  title         = {Engineering Reliable Commit Gates for Agentic {AI}: Cost-Aware Verification Portfolios under Common-Mode Data Failures},
  year          = {2026},
  eprint        = {2609.10969},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 10 September 2026}
}

@misc{williams2026simulatingdeployment,
  author        = {Williams, Marcus and Sheahan, Hannah and Raymond, Cameron and Korbak, Tomek and Pan, Deng and Yang, Peilin and Maksin, Leon and Xie, Ningyi and Guo, Phillip and Kivlichan, Ian and Carroll, Micah},
  title         = {Predicting {LLM} Safety Before Release by Simulating Deployment},
  year          = {2026},
  eprint        = {2607.07184},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 8 July 2026}
}

@misc{dwedar2026safemultirobot,
  author        = {Dwedar, Mohamed and Hafez, Ahmad and Jesser, Alexander and Alanwar, Amr},
  title         = {Safe Multi-Robot Coordination via {VLM}-{LLM} Reasoning and Reachability Analysis},
  year          = {2026},
  eprint        = {2609.27816},
  archivePrefix = {arXiv},
  note          = {Preprint; submission date printed as 18 August 2026 although the identifier is 2609}
}

@misc{lu2026certvla,
  author        = {Lu, Hui and Peng, Zhijie and Lin, Yuqi and Yang, Zaijia and He, Jiaming and Ye, Shuhan and Yu, Yi and Zhu, Hanwei and Shen, Bingquan and Kot, Alex and Jiang, Xudong},
  title         = {{CertVLA}: Certified Defense against Physical Visual Attacks for Vision-Language-Action Models},
  year          = {2026},
  eprint        = {2608.20791},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 21 August 2026}
}

@misc{qin2026harnessing,
  author        = {Qin, Xue and Luan, Simin and See, John and Boukhers, Zeyd and Yang, Cong and Li, Zhijun},
  title         = {Harnessing Embodied Agents: Runtime Governance for Policy-Constrained Execution},
  year          = {2026},
  eprint        = {2604.07833},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 9 April 2026 (v4 10 June 2026)}
}

@misc{singh2026beliefmemory,
  author        = {Singh, Pranav},
  title         = {When Does Belief-Based Agent Memory Help? Reliability-Conditional Updating and Provenance-Capped Poisoning Defense},
  year          = {2026},
  eprint        = {2606.22030},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 20 June 2026}
}

@misc{nakayashiki2026stale,
  author        = {Nakayashiki, Kazuki},
  title         = {When Stale Constraints Go Unchecked: Budgeted Verification Failures in Inherited Agent Memory},
  year          = {2026},
  eprint        = {2608.25553},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 26 August 2026}
}

@misc{wu2026ebl,
  author        = {Wu, Mengting and Wang, Lin and Zhang, Yong and Deng, Jiang},
  title         = {From Intent to Execution Grant: An Execution-Boundary Conformance Profile for High-Risk {AI} Actions},
  year          = {2026},
  eprint        = {2609.11596},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 10 September 2026}
}

@misc{wu2026provably,
  author        = {Wu, Benlong and Zhang, Weiming and Chen, Kejiang and Fang, Han and Yu, Nenghai},
  title         = {Provably Secure Agent Guardrail},
  year          = {2026},
  eprint        = {2605.29251},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 28 May 2026}
}

@misc{nguyen2026vepa,
  author        = {Nguyen, Duy and Miculicich, Lesly and Mishra, Bhavana Dalvi and Li, Shuo and Dvijotham, Krishnamurthy Dj and Bansal, Mohit and Pfister, Tomas and Le, Long T.},
  title         = {{VEPA}: Verified Evolving Formal Policy for Lifelong {LLM} Agent Guardrails},
  year          = {2026},
  eprint        = {2610.12813},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 8 October 2026}
}

@misc{yu2026nomos,
  author        = {Yu, Min-Young and Kim, Tony and Choi, Jang Won},
  title         = {{NOMOS}: Compiling Written Policies into Statically Verified Tool-Call Gates for {LLM} Agents},
  year          = {2026},
  eprint        = {2610.11030},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 8 October 2026 (v2 14 October 2026)}
}

@misc{wen2026inspect,
  author        = {Wen, Di and Yang, Kailun and Guo, Wenhao and Shi, Yitian and Zheng, Junwei and Chen, Yufan and Liu, Ruiping and Wei, Jiale and Rayyes, Rania and Peng, Kunyu},
  title         = {{INSPECT}: Learning Robot View Selection from Assistant Use},
  year          = {2026},
  eprint        = {2609.20615},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 17 September 2026}
}

@misc{huang2025trustsurvey,
  author        = {Huang, Xinyu and Karthick V B, Shyam and Chen, Taozhao and Bryson, Mitch and Chaffey, Thomas and Chen, Huaming and Choo, Kim-Kwang Raymond and Manchester, Ian R.},
  title         = {Trust in {LLM}-controlled Robotics: a Survey of Security Threats, Defenses and Challenges},
  year          = {2025},
  eprint        = {2601.02377},
  archivePrefix = {arXiv},
  note          = {Preprint, submitted 17 December 2025}
}
```

Marked **unverified beyond the search listing, no BibTeX given**: 2606.16788, 2607.28226, 2605.02900, 2609.13231, 2606.00773, 2605.07472, 2608.03924, 2609.00267, 2605.05440.
Author lists are copied from the abstract pages; in `huang2025trustsurvey` the second author's name ("Shyam Karthick V B") is ambiguous as to family name, so check the arXiv listing before camera-ready.

## 7. Limits

* US-only web index; the arXiv ids and dates come from the abstract pages, which this session could read. Several 2610 papers (the last two weeks) may not be indexed yet.
* Only AuthGuard-R, SafeCommit and TMA-NM were read in HTML full text (partly). Every other rating is from the abstract; if a reviewer names one of them, re-read it first.
* Ratings are our judgement against the strongest reading a hostile reviewer could give, as in the earlier review.
* Peer-review status unknown for all entries; they are claims of the authors and unreplicated.

## Addendum 2026-10-23: generative images for simulator realism and data expansion (study QI)
Gap noticed by the user: the literature scan did not cover generative image models. Searches (WebSearch, then the arXiv abstract pages) found, all verified at the abstract level only:
* **ROSIE** (Yu et al., arXiv 2302.11550, RSS 2023): text-to-image editing inpaints unseen objects, backgrounds and distractors into robot demonstrations; the policy (RT-1) is trained on the edited data. Closest in method to QI-G (edit inside a mask), but for training data, not for testing a safety monitor.
* **Cosmos-Transfer1** (Abu Alhaija et al., NVIDIA, arXiv 2503.14492): conditional world generation with segmentation/depth/edge controls for Sim2Real transfer; the same idea as QI-R at larger scale and with geometry controls (our R uses a single image edit prompt, no control signal, and we check pixels instead).
* **Sim2Real Diffusion** (Samak et al., arXiv 2507.00236): latent diffusion maps simulated driving frames to realistic ones, reports a perceptual gap reduction above 40% (their figure, not verified by us); driving, perception metrics, no safety gate.
* **SPIE** (Benarous, Du, Yang, arXiv 2504.12833): post-trains an image-editing diffusion model with AI feedback; one application is making simulated robot scenes more realistic, motivated by policy evaluation in simulation (with SIMPLER, already cited).
* **Synthetic fire/smoke data** (Gaba, arXiv 2511.16617; other work on GAN-generated fire images): generated or composited smoke datasets show a synthetic-to-real domain gap; this supports our own limit: generated fires are not real fires, and a pass on QI-G is not evidence on real photographs.
What we found NOT in the literature (as far as these searches go): using a generative image model to **stress-test a VLM safety gate** under a pre-registered, pixel-checked protocol with the gate and threshold frozen. This is a narrow novelty claim and stays in the supplement.

## Addendum 2026-10-23 (b): correlated errors of VLM ensembles and size dependence of smoke detection (studies JH, JI)
Searched after the user asked for more literature work; both read on the arXiv abstract page (V-abs), not in full text.
* **Hidden Clones** (Bugaud, arXiv 2603.17111, 17 Mar 2026): VLMs of one family make correlated errors; across 17 models from 8 families the ensemble behaves like 2.5-3.6 independent voters. Supports our study-JH finding that the same-family Qwen3-VL judge adds nothing ($\varphi$ 0.75) and that cross-family judges still correlate with the gate. Cited in the supplement (JH Result).
* **SmokeBench** (Qi, Li, Barnes, arXiv 2512.11215, WACV 2026): multimodal LLMs find large smoke but localize early smoke poorly; smoke volume matters more than contrast. Consistent with our fire-size dependence (main Fig. firesize). Cited in the supplement (fire and smoke perception).
* Not found (standard-mode searches, US index): a paper that uses generated images to stress-test a robot safety monitor under a registered protocol (as before), or a paper that reports multi-view look-around reducing missed hazards of a VLM gate. Other hits (I-Perceive 2603.00600, Language as Cost 2508.03138) are active-perception or planning work without a missed-hazard measurement; not cited.

## Addendum 2026-10-24 (c): five Haiku literature scouts, re-verified by the main agent
At the user's request five Haiku agents searched five topics (active perception; calibration and selective prediction; VLM fire detection and generated test data; preregistration, evaluation methodology and judge-error correlation; command grounding and ASR robustness). Their tables are untrusted data: every paper that is cited was re-fetched by the main agent on its arXiv abstract page (V-abs), title, authors and date compared. **Added to the bibliography and cited in the supplement (9):** Kohli 2605.29800 (nine judges, about two independent votes) and Kim et al. 2506.07962 (correlated LLM errors) next to Hidden Clones in the JH reading; Navasardyan et al. 2609.03611 (FailBench: 13 VLM failure detectors, best 0.77 balanced accuracy) and Li et al. 2609.07823 (SAFIRE) in the fire/smoke paragraph; Helbling et al. 2510.21120 (SafetyPairs: counterfactual image pairs by editing) in QI, **the closest prior use of editing to build safety test data; our difference is the registered monitor-level miss and false-stop audit with control edits**; Jia and Lemon 2608.28518 (simulated ASR errors make harmful instructions accepted) and Wang et al. 2404.09754 (LLMs on noisy instructions) in IG; Hu et al. 2603.11072 (OA-NBV) and Podolinsky et al. 2606.09919 (Co-GLANCE) in JK; He 2607.13361 (detector confidence signals presence, not occlusion) in JC as a caution about score-based triggers. **Not cited but noted:** conformal anchors already in the bibliography (Angelopoulos and Bates 2107.07511, Conformal Risk Control 2208.02814, Geifman and El-Yaniv 1705.08500, KnowNo 2307.01928, VAP-TAMP 2604.26988); not re-verified by me and left out: Tibshirani et al. 1904.06019, Barber et al. 2202.13415, Gibbs and Candès 2106.00170 (shift theory), Agarwal et al. 2108.13264 and Henderson et al. 1709.06560 (statistical practice), Badithela et al. 2510.04354, REALM and other sim-to-real benchmarks. **Gaps the scouts found (arXiv, their search only):** no paper on zero-shot VLM detection of small, early or occluded fire other than SmokeBench; no verified paper on unknown-destination handling for instruction-following robots; Japanese or code-mixed robot commands returned nothing.

## Addendum 2026-10-24 (d): rounds 2 and 3 of the Haiku scouts (ten more topics), re-verified by the main agent
Round 2 (safety architectures; multi-view and test-time scaling; disaster robotics; infeasible and out-of-scope instructions; statistics of small-sample safety evaluation) and round 3 (answerability probes and unknown-entity detection; visibility-aware fire detection; simulation, flakiness and audit; N-version and multi-model verification; prompt injection and trust in advice). About 140 rows reported by the agents; **every paper cited was re-fetched on its arXiv abstract page by the main agent** (V-abs). Cited in the supplement (34 new): CORE 2602.19983 and conformal shielding 2506.17275 (nearest formal bounds under imperfect perception; neither has a fail-closed yes/no gate or a tighten-only advice channel); ZONDA 2607.21025, ViCrop-Det 2604.26806, ZoomEye 2411.16044, Seeing Isn't Knowing 2605.30557, multi-view hallucination 2603.23934, the decoding-format audit 2608.01207 (matched-budget warning); HAZARD 2401.12975, ESARBench 2605.01371, Before We Trust Them 2601.05529, SafeAgentBench 2412.13178, EgoSafetyBench 2607.00218; TRUST 2609.37554, Wagner 2607.08456, Lavi 2509.22449, FeasiGen 2605.28532, VLN-NF 2604.10533, CLARA 2306.10376, AbstentionBench 2506.09038, grammar-constrained parsing 2604.04233; McDonnell 2607.19899 (disagreement escalation misses correlated failures); Mandujano Reyes 2608.22659, Blum and Hardt 1502.04585, Luo et al. 2109.14082, SureSim 2510.04354, Søgaard et al. 2302.10086; Amini et al. 2311.18768 and Afzal et al. 2004.07368 (flaky simulators). **Threat ratings that changed the paper:** SmokeBench (size dominates contrast) led to the size-against-hiding analysis (the hard class is a small-fire class; hiding cannot be separated at matched area); Wagner and Lavi (answerability probes) led to the registered probe experiment IJ; the multiple-comparison literature led to the Holm/BH table (GM does not survive Holm, JL is the fresh confirmation); Hidden Clones, Kohli and Kim led to the double-fault and Q-statistic table. **Not cited (not re-verified or weak fits):** the rest of the scouts' rows. **Still not found:** a psychometric study of detection probability against object area for VLMs; Japanese facility-name handling for robot commands; ROS 2 twist-mux or velocity-limiter studies on arXiv.

## Addendum 2026-10-24 (e): round 4 (five more topics), re-verified by the main agent
Topics: human factors of read-back and oversight; token-probability scoring of VLMs; robustness to lighting, clutter and rendering; assurance cases and machine-checked guarantees; Japanese-language evaluation. Cited in the supplement (23 new): Scarbro and Mangal 2604.20728 (interval POMDP shielding), Cleaveland et al. 2503.18077, Corsi et al. 2606.23754 (FEARL), Jackson et al. 2104.06178 (certified control), Hawkins et al. 2102.01564 (AMLAS), Gohar et al. 2606.11462 (defeater cards): **the nearest probabilistic bounds under imperfect perception; none machine-checks the bound against the deployed gate code** (no arXiv paper on that was found); Recchia 2507.19486, Horowitz and Kahn 2306.16507, Turan 2606.08919 (oversight is not free; the read-back is untested); Tian et al. 2305.14975 (verbalised confidence may beat token probabilities), Atabuzzaman et al. 2509.16805, Dumpala et al. 2410.13030 (option and prompt bias), POPE 2305.10355, VQAScore 2404.01291; VLM-RobustBench 2603.06148, PCRI 2509.23879, Usama et al. 2504.13690, Fire360 2506.02167; ReLI 2505.01862 (cross-lingual language-to-action, the nearest to our Japanese claim), Karita et al. 2306.04530 (lenient scoring of Japanese spelling variants), JAMMEval 2604.00909, Talk2Agent 2609.38867, Nowrin and Vertanen 2410.20564. **Corrections of the scouts' rows:** one scout described 2504.13690 as showing that brightness barely matters; its abstract says text recognition and object reasoning fail in different ways, so only that is used. **New analyses prompted:** `scripts/permutation_agreement.py` (the two permuted supply questions disagree on 26 of 1,887 XD images and 20 of 1,440 JI images; the second pass is about one point less accurate) and `scripts/smoke_strata.py` (every residual miss of the left-only arm and of the extra-view arm is in a world with a smoke plume). **Not found:** Japanese shelter or facility-name parsing; machine-checked monitors against deployed code; UL 4600 or SOTIF work from 2024-2026 on arXiv.

## Addendum 2026-10-24 (f): round 5 by the main agent (no subagent), risk-aware view selection
Searched: uncertainty- or risk-triggered next-best-view for robot safety. Verified on the arXiv abstract pages: 2403.11396 (RaEM: risk measures prioritise safety-critical unknown regions for FisherRF view selection, v2 2025-01-17), 2510.06481 (risk-averse path refinement on Gaussian-splat risk maps with Riemannian next-best-view optimisation, 2025-10-07), 2609.23100 (Splat-CBF: information-gain and risk barrier functions in one QP, 2026-09-19). None scores views with a VLM hazard gate or reports a registered closed-loop delivery budget; they place JK among risk-aware active perception (cited in the JK subsection). A search for read-back studies of robot instructions found only correction-dialogue work (2211.10168, 2204.05186), not cited: they correct a plan after acting, not confirm a parse before acting.

## Addendum 2026-10-24 (g): round 6, Haiku scouts (five topics), re-verified by the main agent
Topics: conformal calibration of VLM/LLM decisions under shift; fire and smoke vision and fire robots; runtime safety layers for LLM robots; statistical methodology of robot evaluation; instruction grounding and clarification. Scouts returned 67 candidates; 22 were already cited (dedup by arXiv id). Seventeen new papers were opened on their arXiv abstract pages by the main agent and cited: 1904.06019, 2202.13415, 2505.24693, 2512.14727, 2305.18404 (calibration bound paragraph); 2309.09919, 2606.31045, 2604.07833, 2209.14030 (safety architectures); 2408.03515 (injection); 2108.13264, 2405.05439, 2603.13616 (multiplicity/evaluation); 2508.05148, 2604.12831, 2512.11215, 2511.02495 (fire). Not cited: two withdrawn papers (2509.00054, 2412.16186), detector-only YOLO papers, a single-author SMT essay (2603.21149), items not on arXiv. Scout gaps confirmed: no paper found on read-back confirmation of a parsed robot instruction, on robots refusing unlisted place names, or on pre-registration in robotics.

## Addendum 2026-10-24 (h): round 7, Haiku scouts (five topics), re-verified by the main agent
Topics: hidden-state probes for unanswerable/unknown inputs; simulation testing of perception; humanitarian and disaster robotics; multi-view fusion, correlated judges and cascades; trust in advice sources and memory poisoning. 66 candidates, 5 already cited. Eighteen new papers opened on arXiv by the main agent and cited: probes 2310.11877, 2304.13734, 2310.06824, 2410.02707, 2506.08572, 2510.09033 (IJ draft); fusion/cascades 2305.05176, 2502.09054, 2510.11822, 2011.11156 (JI/JC section); advice and memory 2507.18808, 2003.02144, 2209.12285, 2512.16962, 2606.04329; simulation/VLM safeguards 2603.14367, 2601.08470, 2605.06311. Verified but not cited yet: 2406.15927, 2212.09354, 2510.16692 (disaster-robot field lessons and responder trust, candidates for the practicality discussion). Gaps: no paper on max-versus-mean fusion of views for a VLM safety decision; no ground robot for relief-depot stock checks.

## Addendum 2026-10-24 (j): round 9, Haiku scouts (five topics), re-verified by the main agent
Topics: multi-view fusion (max/OR rule); inventory-auditing robots; VLM logit classification; delivery-robot safety; fire simulation, thermal and radar. 63 candidates, 5 already cited. Fourteen opened on arXiv by the main agent and cited: 2402.14499, 2505.15323, 2609.27408, 2402.13213 (scoring paragraph); 2603.19063, 2602.19108, 1911.00398, 2305.17705, 2412.10699 (external validity); 2506.05357, 2310.14063, 2610.01283 (stale records, shelf auditing); 1508.02253, 2407.11935 (OR-rule fusion in JI/JC). Gaps: no paper on wrong-item delivery errors, on VLM shelf verification before delivery, or on sim-to-real transfer for flame (as opposed to smoke) detection.

## Addendum 2026-10-24 (k): round 10, Haiku scouts (five topics), re-verified by the main agent
Topics: safety of LLM agents that plan; statistics of rare failures with few trials; local/edge foundation models on robots; robot explanations and their faithfulness; typographic and physical prompt injection. 68 candidates, 7 already cited. Sixteen opened on arXiv by the main agent and cited: 2603.01414, 2506.14697, 2503.08663, 2406.08824 (planning agents vs our closed-question gate); 2404.09705, 2303.16010, 2607.04681, 2505.23945 (report is shown, never decides); 2504.04893, 2601.17383 (scene text); 2505.09477, 2601.14921 (local inference); 1908.06540, 2110.10718, 2505.02274, 1811.00145 (what 100 worlds can certify). Gaps: no OCR-masking defence evaluated in embodied settings; no comparison of Clopper-Pearson and Bayesian bounds for robot certification.
