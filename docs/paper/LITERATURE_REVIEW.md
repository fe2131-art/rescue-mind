# Literature review: stress test of the novelty claims N1-N4

Date of search: 2026-10-17. Scope: 2018-2026 (plus classical foundations), robotics (ICRA/IROS/RSS/CoRL/RA-L/T-RO/HRI), ML and security
(NeurIPS/ICLR/ICML/USENIX/CCS/S&P/SaTML/ICSE), formal methods and online algorithms (ICML/NeurIPS/AAAI/SODA/JACM/TALG).
Bib keys in `code font` are in `references.bib` (44 entries were added by this review; the others were already there).

## 0. How to read this document

Claims under test (from the task):
* **N1** Advice monotonicity: everything the robot did not perceive itself at the station (memory, peers, inventory, operator text) is typed
  *advice*; advice may only reorder visits or tighten thresholds, never remove a check; hence P(unsafe | any advice) <= k*eps with a bounded
  denial-of-service cost; enforced in code, recomputed by an audit, evaluated in closed loop (study A) against naive and LLM-filter baselines.
* **N2** Check-preserving cross-mission memory for a pre-action VLM gate (campaign H).
* **N3** Active look-around (0.4 m sideways) as the fix for VLM misses of partly hidden hazards.
* **N4** Fail-closed closed-set log-prob scoring with permuted options plus an independent velocity guard; pre-registered closed-loop
  evaluation with ground-truth audits; prediction-then-test of a mission model (study V).

Per entry, the line "Weakens" gives the effect on the novelty of the named claim: **none** (supports us or unrelated), **partial** (same idea
in part, or same idea in another setting), **strong** (a reviewer can fairly say the claim is already made). "Read" says what was actually
read. Method: papers were located with web search and then retrieved as full text (arXiv HTML) into a local scratch folder and read at the
passages named. "Full text retrieved" means the whole paper was available and the cited sections were read; it does not mean every line was
read. "Abstract only" means exactly that. Classical foundations (Section 10) were verified bibliographically (Crossref) but not re-read.
Numbers quoted come from the cited passage. The search tool is US-only and arXiv-heavy; IEEE Xplore and ACM pages were not read. Anything
that appeared only in a search listing is marked as such.

**Bottom line (honest version).**
1. The *principle* behind N1 (untrusted input must not be able to relax a trusted check) is established in three older literatures:
   integrity information-flow control (Biba, Denning; for LLM agents Fides, CaMeL), attenuation-only capabilities (macaroons) and
   supervisory control or shielding (a supervisor can only disable). Fides states it as integrity *non-interference* and enforces it
   deterministically. A reviewer from security will say N1 is a weakened form of that. What we did not find anywhere is the specific
   combination: a typed advice interface at a *perception-grounded, probabilistic* pre-action gate of a physical robot, with the bound
   k*eps for every advice set, an explicit availability (denial-of-service) cost, and a ground-truth-audited closed-loop comparison with a
   naive and a filter baseline. That is a defensible, narrower claim.
2. The theoretical frame that matches the *shape* of N1 best is not security but algorithms with predictions (consistency and robustness).
   Dinitz et al. (predictions change running time, never correctness) and Lykouris and Vassilvitskii (naively following the oracle is
   unbounded) are the same idea in another domain. We should cite them and use their vocabulary.
3. N2 and N3 are the weakest as *novel mechanisms*: arrival verification of a remembered target and VLM-driven viewpoint change are
   published (OpenBelief-Nav, VAP-TAMP, OA-NBV). Their value is the safety invariant, the bound and the pre-registered paired evidence.
4. N4's parts are individually known (next-token scoring and option randomisation in KnowNo; Simplex-style separation; shields).
   We found no prior pre-registered closed-loop robotics evaluation of this kind and no prior prediction-then-test of a mission model, but
   absence in a US-only, arXiv-heavy search is weak evidence.

---

## 1. Summary table

| Work (key) | N1 | N2 | N3 | N4 | Read |
|---|---|---|---|---|---|
| Fides (`costa2025fides`) | strong (principle) | partial | - | - | full text |
| CaMeL (`debenedetti2025camel`) | partial | - | - | - | full text |
| Design patterns (`beurerkellner2025patterns`) | partial | - | - | - | full text, partly |
| TMA-NM memory authority (`louck2026tma`) | partial | partial-strong (memory as untrusted, act=none) | - | - | full text, partly |
| RoboGuard (`ravichandran2026guardrails`) | partial | - | - | partial | full text, partly |
| RoboSafe (`wang2025robosafe`) | partial | partial (memory only adds blocking predicates) | - | - | full text, partly |
| Dinitz warm-start (`dinitz2021faster`) | partial (analogue) | - | - | - | full text, partly |
| Lykouris and Vassilvitskii (`lykouris2021competitive`) | partial (analogue) | - | - | - | full text, partly |
| Purohit et al. (`purohit2018improving`), survey (`mitzenmacher2020algorithms`) | partial (analogue) | - | - | - | full text, partly |
| Li et al. LQ control (`li2022robustness`) | partial | - | - | - | full text, partly |
| MetaBSG (`xu2023untrustworthy`) | partial (robotics precedent) | - | - | - | full text, partly |
| Black-Box Simplex (`mehmood2022blackbox`) | partial | - | - | partial | full text, partly |
| OpenBelief-Nav (`nguyen2026openbelief`) | - | partial-strong (concept) | - | - | full text, partly |
| VAP-TAMP (`oloo2026vaptamp`) | - | partial | partial | partial | full text, partly |
| OA-NBV (`hu2026oanbv`) | - | - | partial | - | abstract only |
| Samarakoon et al. (`samarakoon2026paper`) | - | - | - | partial (study S) | full text, partly |
| Embodied-security survey (`liu2026embodiedsecurity`) | none (states the gap) | none | - | - | full text, partly |
| AI control (`greenblatt2024control`) | partial (evaluation method) | - | - | partial | full text, partly |
| KnowNo (`ren2023knowno`) | - | - | - | partial | full text, partly |

---

## 2. Algorithms with predictions (learning-augmented algorithms)

This is the closest *theoretical* analogue of N1: a decision procedure receives untrusted advice and must (i) profit when it is right
(consistency) and (ii) not be hurt beyond a bound when it is wrong (robustness).

**`lykouris2021competitive`. Lykouris, T., Vassilvitskii, S. Competitive caching with machine learned advice. JACM 68(4), 2021 (ICML 2018).**
* What it does: introduces the framework in which an online algorithm gets a black-box learned oracle, and defines beta-consistency
  (competitive ratio when the oracle is perfect) and alpha-robustness (competitive ratio as a function of oracle error, capped near the
  advice-free bound). Shows that blindly following the oracle (Belady rule) is optimal when the oracle is perfect but unbounded when it is
  not, and gives a Marker-based algorithm that is capped by O(log k).
* Relation: N1 is a *hard-robust* instance of this paradigm for safety. Advice is used only where it cannot affect correctness (order),
  so safety robustness is exactly the advice-free bound, and only time degrades. The authors' "naively following the oracle may lead to very
  poor performance, even when the average error is quite low" is the same argument we make for the naive-advice arm.
* Weakens: **partial** (N1 framing; not a safety-of-a-probabilistic-check result). A theory-oriented reviewer will say "this is
  consistency/robustness with robustness = 1 for safety".
* Read: full text retrieved; abstract, Sec. 1 (desiderata), Sec. 2.2 (definitions), Sec. 3 (the naive Belady algorithm and why it is
  unbounded).

**`purohit2018improving`. Purohit, M., Svitkina, Z., Kumar, R. Improving online algorithms via ML predictions. NeurIPS 2018.**
* What it does: ski rental and non-clairvoyant scheduling with a predictor; explicit trade-off parameter lambda between consistency and
  robustness; shows that naive use of predictions gives a consistent but non-robust algorithm.
* Relation: same as above; "a risk-averse decision maker may choose a higher lambda, limiting the benefit of the predictions but also
  the additional cost when they turn out to be incorrect" (stated in the survey below) is the trade-off our design fixes at the safe end for the
  safety dimension.
* Weakens: **partial** (analogue). Read: extended arXiv version (2407.17712), Sec. 1 (definitions of gamma-robust and beta-consistent,
  the naive warm-up). The NeurIPS text itself was not opened.

**`mitzenmacher2020algorithms`. Mitzenmacher, M., Vassilvitskii, S. Algorithms with predictions. In Beyond the Worst-Case Analysis of Algorithms, CUP 2020 (arXiv 2006.09123).**
* What it does: survey chapter; alpha-consistent, beta-robust; ski-rental worked example; caching.
* Relation: the canonical reference to cite for the vocabulary. States the tension between consistency and robustness that a "risk-averse
  decision maker" resolves toward robustness.
* Weakens: none (reference). Read: full text retrieved; Secs. 1-2.

**`antoniadis2023online`. Antoniadis, A., Coester, C., Eliáš, M., Polak, A., Simon, B. Online metric algorithms with untrusted predictions. ACM TALG 19(2), 2023 (ICML 2020).**
* What it does: framework for metrical task systems in which predictions are explicitly *untrusted*; robustification by combining with a
  worst-case algorithm.
* Relation: terminology ("untrusted predictions") and a general robustification construction; no safety predicate.
* Weakens: none-partial. Read: **abstract only** (search listing and PMLR page).

**`dinitz2021faster`. Dinitz, M., Im, S., Lavastida, T., Moseley, B., Vassilvitskii, S. Faster matchings via learned duals. NeurIPS 2021.**
* What it does: uses learned dual variables to warm-start the Hungarian algorithm; the output is the exact optimum, only the running time
  depends on prediction quality.
* Relation: the *closest structural twin* of N1 inside the predictions literature: the paper says that even with a poor prediction "our
  method has worst-case running time that is never worse than that of the Hungarian algorithm", and that it computes "the exactly optimal
  solution" while using predictions only to improve running time. Replace "optimal solution" by "check" and "running time" by "number of
  wasted visits" and one gets Proposition 2. It is the right citation for the sentence "advice may change cost, never the decision rule".
* Weakens: **partial** (analogue; deterministic algorithm, no perception, no adversary). Read: full text retrieved; abstract and the
  contribution paragraph of Sec. 1.

**`li2022robustness`. Li, T. et al. Robustness and consistency in linear quadratic control with untrusted predictions. POMACS 6(1), 2022 (SIGMETRICS; arXiv 2106.09659).**
* What it does: LQ control with black-box predictions; lambda-confident controller; competitive ratio 1 + min{O(lambda^2 eps) + O((1-lambda)^2),
  O(1) + O(lambda^2)}; self-tuning of lambda; examples include a robotic tracking problem. States that its work "represents the first work in
  the context of control" on this trade-off and motivates it by safety-critical applications ("catastrophic... unbounded competitive ratio").
* Relation: control-side precedent for "untrusted predictions with adversarial guarantees". Differs: continuous cost bound, no discrete
  safety predicate.
* Weakens: **partial**. Read: full text retrieved; abstract, Sec. 1, Theorem 2.2 statement.

**`eberle2022robustification`, `gouleakis2023learning`. Eberle et al., Robustification of online graph exploration methods. AAAI 2022. Gouleakis, Lakis, Shahkarami, Learning-augmented online TSP on the line. AAAI 2023.**
* What they do: consistency/robustness for robot-style exploration (graph exploration, motivated by search-and-rescue robots) and for routing;
  the algorithm interpolates between "follow the prediction" and a classical algorithm (Nearest Neighbour).
* Relation: closest *robot-routing* instances: advice about the order in which to visit. Our reorder-only memory/location advice is a special
  case in which the "classical algorithm" is "check every station you reach".
* Weakens: none-partial. Read: Eberle full text retrieved (abstract, Sec. 1: Theorem 1 gives kappa(3+4 lambda)-consistent and
  (1+1/(2 lambda))(ceil(log n)+1)-robust); Gouleakis **abstract only**.

**`xu2023untrustworthy`. Xu, Z., Lin, X., Tzoumas, V. Leveraging untrustworthy commands for multi-robot coordination... a bandit submodular maximization approach. arXiv 2309.16161.**
* What it does: external commands (from human operators or ML) are "untrustworthy in that their performance guarantees, if any, are
  unknown"; MetaBSG learns whether to follow the commands or a guaranteed fallback and "enjoys performance guarantees even when the external
  commands are arbitrarily bad"; "can be interpreted as robustifying the untrustworthy commands".
* Relation: the one *robotics* paper we found whose headline is "untrusted operator/ML advice, guarantee holds when the advice is
  arbitrarily bad". Differs: the guarantee is a regret bound on a coverage objective, obtained by *learning to ignore* the advice; ours is
  a safety predicate obtained *by construction* (advice has no path to the decision) plus a measured cost.
* Weakens: **partial** (precedent for the claim "untrusted advice with a guarantee" in robotics). Read: full text retrieved; abstract,
  Sec. 1, Fig. 1. Preprint, no venue found.

---

## 3. Information-flow control, capabilities and structural defences for LLM agents

**`costa2025fides`. Costa, M. et al. Securing AI agents with information-flow control (Fides). arXiv 2505.23643.**
* What it does: formal model of agent planners; confidentiality and integrity labels on a lattice; deterministic policy engine. Policy
  P-T ("trusted action") permits a consequential tool call "only if the model's decision to call the tool is based exclusively on inputs from
  trusted sources" (Sec. 4.3). Sec. 4.4: for the binary integrity lattice, non-interference "prevents untrusted data U from flowing into
  trusted sinks, which includes consequential control flow decisions and is sufficient to prevent PIAs". Selective hiding/revealing of
  variables to recover utility; evaluated on AgentDojo (utility falls under stricter policies; Sec. 8).
* Relation: this is N1's principle, stated formally and enforced deterministically, for software agents. Differences that remain ours:
  (a) Fides forbids *any* influence of untrusted data on a consequential decision; we allow influence in one direction only (reorder, tighten),
  which is why advice can still save time; formally ours is a bounded, one-sided relaxation of non-interference (a restricted endorsement), not
  non-interference. (b) The protected decision in Fides is a deterministic policy over labels; ours is a *probabilistic perceptual* check, so the
  guarantee is k*eps rather than 0. (c) Physical gate, cost bound and closed-loop evaluation. The honest consequence: **strict IFC applied
  to our system equals our no-advice arm**, because any advice in the context would taint the delivery decision and be ignored; study A
  therefore already contains the strict-IFC baseline implicitly, and we should say so.
* Weakens: **strong for the principle**, none for the instantiation.
* Read: full text retrieved; Sec. 1, 4.1, 4.3, 4.4, 5, 8.

**`debenedetti2025camel`. Debenedetti, E. et al. Defeating prompt injections by design (CaMeL). arXiv 2503.18813.**
* What it does: privileged LLM plans from the trusted query only; a quarantined LLM parses untrusted data without tools; a custom interpreter
  tracks a data-flow graph and attaches capabilities, enforcing policies at tool calls. 77 % of AgentDojo tasks solved with provable security
  vs 84 % undefended.
* Relation: structural, filter-free defence; "untrusted data can never impact the program flow". Sec. 3.1 lists non-goals: CaMeL "cannot
  defend against text-to-text attacks which have no consequences on the data flow", and Sec. 1 notes that arguments (data flow) can still be
  manipulated even if the control flow is protected. The same holds for us: scene text and *what the camera sees* are outside the
  guarantee, which we already state (study S).
* Weakens: **partial** (same design philosophy, other domain, other property: confidentiality/exfiltration rather than a safety check).
* Read: full text retrieved; Sec. 1-3.1, 5, 7, 9.

**`beurerkellner2025patterns`, `willison2023dual`. Beurer-Kellner, L. et al. Design patterns for securing LLM agents against prompt injections (arXiv 2506.08837); Willison, S. The Dual LLM pattern (blog, 2023).**
* What they do: catalogue of patterns (action-selector, plan-then-execute, LLM map-reduce, dual LLM, code-then-execute, context minimisation)
  that "limit the capabilities of agents in principled ways"; they argue that filter/guardrail defences "remain fundamentally heuristic and cannot
  guarantee prevention of all attacks".
* Relation: justifies the LLM-filter baseline of study A as the *state-of-practice heuristic* and our typed interface as an instance of the
  "limit what untrusted data can influence" family. Plan-then-execute and action-selector are control-flow versions of "advice may reorder but
  not add actions".
* Weakens: **partial**. Read: full text retrieved; abstract, Sec. 1, pattern descriptions (partly). Willison's post: not opened (identified
  through search listing; date 2023-04-25).

**`greenblatt2024control`. Greenblatt, R., Shlegeris, B., Sachan, K., Roger, F. AI control: improving safety despite intentional subversion. ICML 2024.**
* What it does: evaluates "protocols" for using a powerful untrusted model with a weaker trusted one under a red team that replaces the
  untrusted model with an attack policy; reports safety (never submitting a backdoor) and usefulness. Trusted monitoring, trusted editing,
  untrusted monitoring.
* Relation: methodological precedent for study A: the adversary is part of the evaluation (our "poison" conditions), safety and usefulness
  are reported together (our A1 and A2). Differs: text-only coding tasks, no physical gate.
* Weakens: **partial** (evaluation design, N1/N4). Read: full text retrieved; abstract and Sec. 1.

**`kambhampati2024llmmodulo`. Kambhampati, S. et al. LLMs can't plan, but can help planning in LLM-Modulo frameworks. ICML 2024.**
* What it does: LLM as candidate generator, a bank of external critics as hard verifiers; "plans an LLM helps generate... have soundness
  guarantees because of the external sound critics" (Sec. 3).
* Relation: "proposes / disposes" architecture, equal in spirit to "memory proposes, perception disposes". Our critic is a probabilistic VLM, so
  soundness becomes a measured eps; the paper does not treat it.
* Weakens: **partial** (N1/N2 framing). Read: full text retrieved; Sec. 1 and 3.

**Evaluation of filters: `nasr2025attacker`, `wallace2024hierarchy`, `debenedetti2024agentdojo`.**
* Nasr et al.: adaptive attackers bypass published jailbreak/prompt-injection defences (abstract: the defences were evaluated "against a
  static set of harmful attack strings, or against computationally weak optimization methods"). Wallace et al.: train the model to prioritise
  privileged instructions. AgentDojo: benchmark of injection attacks and defences for tool-using agents.
* Relation: back the claim that an LLM filter is the wrong thing to rely on against an adaptive adversary and justify including it only as
  a baseline. Do not oversell: our filtered-advice baseline is not adaptively attacked unless study A includes an adaptive condition.
* Weakens: none. Read: **abstracts only** (all three).

---

## 4. Runtime assurance, shielding and guardrails for LLM/VLM-driven robots

**`mehmood2022blackbox`. Mehmood, U. et al. The Black-Box Simplex architecture for runtime assurance of autonomous CPS. NFM 2022 (arXiv 2102.12981).**
* What it does: an unverified advanced controller and a baseline controller; a decision module checks command sequences at run time; the
  authors "prove the architecture is safe" (safety theorem) and "transparent" (when the advanced controller is good, it appears to have full
  control) (Sec. 2.2).
* Relation: safety plus transparency theorems are the control-theory twin of robustness plus consistency, and of our Prop. 2 plus the A2
  time-saving result. Seto 1998 and Sha 2001 (already cited) are the origin.
* Weakens: **partial** (N1 architecture: untrusted component cannot violate the trusted check; N4 independent guard). Read: full text
  retrieved; abstract, Sec. 1, 2.2.

**`ravichandran2026guardrails` (RoboGuard). Ravichandran, Z. et al. Safety guardrails for LLM-enabled robots. RA-L 11(4), 2026 (arXiv 2503.07885).**
* What it does: a root-of-trust LLM, "shielded from malicious prompts", grounds fixed safety rules in the robot's world model as temporal-logic
  specifications; control synthesis resolves conflicts with the (possibly jailbroken) plan; unsafe plan execution from over 92 % to below 3 %,
  also against adaptive attacks.
* Relation: shares the structural idea (the user prompt cannot reach the safety specification). Differences: it guards the *plan*; it assumes
  the world model is correct (Sec. V, first limitation: "RoboGuard requires an accurate world model... addressing this vulnerability requires
  perception safeguards"). Ours is exactly such a perception safeguard at the station, and gives advice a defined, harmless effect.
* Weakens: **partial** (N1 in its robot-guardrail form). Read: full text retrieved; abstract, Sec. I-III, V.

**`wang2025robosafe` (RoboSafe). Wang, X. et al. arXiv 2512.21220.**
* What it does: runtime guardrail for VLM embodied agents with a long-term *safety memory* of past experiences from which executable
  safety predicates are generated; a block is raised if *any* predicate fires (Eq. 6, a disjunction), and the memory is extended with
  executable items (Eq. 7). Reports that ThinkSafe blocks too much (capability-preserving ESR 24.11 %) and AgentSpec preserves capability (91.22 %).
* Relation: memory can only *add* blocking conditions to a guard (a monotone, tighten-only use of memory); the retrieved items are
  LLM-generated and unaudited, no staleness or poisoning analysis, no bound, no mission-level evaluation.
* Weakens: **partial for N2's mechanism** (memory that tightens a guard). Not for the invariant, the bound or reordering.
* Read: full text retrieved; Sec. 4.1-4.2, 5.2.

**Other guards, read less deeply.**
* `wang2026agentspec` (AgentSpec, ICSE 2026): DSL of trigger-predicate-enforcement rules; "eliminates all hazardous actions in embodied agent
  tasks" on SafeAgentBench; static rules were "largely ineffective" in RoboSafe's comparison. Relation: rule-level runtime enforcement, an
  example of a monotone (deny-only) enforcement layer. **Partial**; abstract and Sec. 1.
* `yang2024safetychip` (Safety Chip, ICRA 2024): LTL constraints prune unsafe actions in LLM plans. **Partial**; description taken from the search listing (the text was retrieved but not read).
* `obi2026safegate` (SafeGate, 2026): deterministic authorize/defer/reject gate over structured hazards extracted from *commands*, with
  contracts verified by Z3; operates on text, not on what the camera sees. **None-partial** (N1: a deterministic gate over untrusted text);
  abstract and decision rules read.
* `rodriguez2026safetap` (SafeTap, KR 2026): shield synthesised for an LLM-commanded quadruped; "a corrective mechanism that monitors the
  actions proposed by an untrusted component (here, an LLM) and overrides them". **Partial** (N4's independent guard, N1's untrusted
  proposer); abstract and Sec. 1.
* `hafez2025safe`: data-driven reachability guarantees for an LLM navigating a robot. **None-partial**; abstract only.

---

## 5. Safe use of untrusted priors and advice (RL, POMDP, estimation)

**`asmar2025learning`. Asmar, D. M., Kochenderfer, M. J. Learning to trust: Bayesian adaptation to varying suggester reliability. arXiv 2511.12378.**
* What it does: puts the reliability of an advice source in the belief state of a POMDP and infers it by Bayesian inference; adds an "ask" action.
* Relation: the *alternative* to structural monotonicity is to learn how much to trust the advisor. It improves performance on average but
  carries no worst-case guarantee against an adversary that behaves reliably first. A fair extra baseline for study A.
* Weakens: **partial** (alternative design, not a guarantee). Read: abstract and keyword search of the text.

**`laroche2019safe`, `wendl2026sooper`, `fawzi2014secure`.**
* SPIBB: guarantee "at least as well as the baseline" by bootstrapping from the baseline when uncertainty is high. SOOPER: safe exploration that
  falls back to a conservative policy prior, with a proof of safety throughout learning. Fawzi et al.: state estimation that is correct as long as at
  most a bounded number of sensors are attacked.
* Relation: "never worse than the trusted baseline" in RL, and the classical sensor-attack bound whose assumption (at most q corrupted sensors) is
  *stronger* than ours (advice is not a sensor, so no bound on how much of it is corrupted is needed).
* Weakens: none-partial. Read: abstracts only.

---

## 6. Attacks and defences on embodied agents (untrusted channels, scene text)

**`samarakoon2026paper`. Samarakoon, S. M. B. P. et al. Hijacking robots with a piece of paper. arXiv 2608.05715.**
* What it does: 20 attack prompts in four categories, 5,670 trials, GPT-4o / Gemini 2.5 Flash / Qwen3-VL-32B; attack success 27.0 / 29.4 / 5.0 %.
  Three mitigations: D1 prompt-based "ignore scene text", D2 two-stage verification (a second call of the same model), D3 OCR-based text
  masking. D3 gives "0.0 % ASR across all three models (0 successful attacks in 5,400 defense trials)"; D2 cuts ASR by 85-100 %.
* Relation: nearest to study S. **Threat to our framing of scene text as "outside the guarantee"**: a cheap masking baseline reaches zero
  attack success on their (task-planning, static-image) benchmark; a reviewer will ask why we do not include it. Counter-arguments we can
  test: masking removes legitimate labels and signage that are part of the task (CHAI and the wearable-glasses paper make this point), and
  masking cannot address attacks that are not text (e.g. a fire drawn as a decal, a fake item).
* Weakens: **partial** (study S positioning, not N1). Read: full text retrieved; abstract and the mitigation section (Table 4).

**`burbano2026chai`. Burbano, L. et al. CHAI: command hijacking against embodied AI. SaTML 2026 (arXiv 2510.00181).**
* What it does: attacks with deceptive signs on drones, driving and robotic vehicles. In the discussion: authentication of instructions
  "presumes a closed and well-defined set of trusted entities... an assumption that breaks down in open environments such as public streets,
  or disaster zones", and OCR/text filtering "undermines the very capabilities that motivate the use of LVLMs"; embodied agents "must decide
  whether an inferred instruction is appropriate given their physical state, environment, and mission objectives".
* Relation: supports the disaster-zone motivation for not relying on authentication of advice and for a structural defence; does not offer one.
* Weakens: none (supports). Read: full text retrieved; abstract and Defenses/Discussion.

**`liu2026breaking`, `nagaraja2026prompts`, `chang2026trustboundary`, `li2026devil`.**
* Liu et al. (arXiv 2608.16806): planner-visible *environment state text* is an injection channel; future work lists "state-provenance tracking,
  cross-modal consistency checking, and execution-time verification". Nagaraja et al. (2608.00747): prompt injection propagates between agents of a
  multi-agent robot system through shared prompt structures; attack study only. Chang et al. (2604.19844): "trust boundary confusion" for visual
  injections; reports that six existing defences "suffer severe fail-closed utility loss" (they reject useful signs too) and proposes a multi-agent
  perception/judgement split with robustness guarantees under adversarial perturbations (randomized smoothing); reduces injection success to about 3 % while keeping over 95 %
  of helpful cues. Li et al. (2607.10269): physical prompt injection on smart-glasses VLMs; mask-based filter and detector.
* Relation: confirm that provenance and trust boundaries are being worked on for embodied systems *concurrently*; Chang et al. is the nearest
  defence to a typed trust boundary for *visual* input (but a learned, multi-agent arbiter, no structural bound, no closed loop). Their
  "fail-closed utility loss" is exactly the availability cost that our cost bound quantifies for advice.
* Weakens: **partial** (concurrent work; scene-text defence). Read: Liu, Chang full text retrieved (abstract, Sec. I-II, V partly); Nagaraja and
  Li **abstract only**.

**`liu2026embodiedsecurity` (survey). Liu et al. Security of foundation-model-powered embodied agents. arXiv 2608.16843.**
* What it says that matters here: Sec. 7.2: "Embodied systems must decide whether the information is authorized to alter control flow...
  Scene text saying 'turn left', a RAG document saying 'ignore previous instructions', or another robot claiming 'the target is safe'... should
  nevertheless have different privileges... evolve from content filtering toward provenance-aware privilege control: source identity,
  authority, integrity, freshness, and the set of actions that each source may influence". Memory poisoning (AS03) and multi-robot claims (AS11)
  are called sparse in the literature (2 of 58 attack records cover AS03).
* Relation: this is the *gap statement* for N1 written by third parties, in August 2026. It supports novelty today and signals that others will
  fill it. It also says the idea is "the direction the field should go", which a reviewer can read as "obvious".
* Weakens: none (supports; time-sensitive). Read: full text retrieved; Sec. 3.1, 4 (AS03-AS06, AS10-AS11), 7.2-7.3.

**`chen2024agentpoison`, `dong2025minja`, `robey2025jailbreaking`, `zhang2025badrobot`, `greshake2023indirect`.** Already in the bib (attacks that motivate
the threat model). Not re-read here.

---

## 7. Memory for embodied agents: poisoning, authority, verification at arrival

**`louck2026tma`. Louck, Y. Securing LLM-agent long-term memory against poisoning: non-malleable, origin-bound authority (TMA-NM). arXiv 2606.24322.**
* What it does: authority of a memory item is fixed at write time from its origin; items derived from untrusted origins keep the maximum untrust
  level and are "act=none" at the act gate "no matter how benign the resulting" content; elevation only through corroboration by at least two
  independent principals; three machine-checked theorems (content/lineage defences cannot be sound under laundering; write-time origin binding
  is necessary and, with non-malleability, sufficient); 0 % attack success on a benchmark of eight models; single author, preprint.
* Relation: the *memory* analogue of N1 in IFC clothing: untrusted memory may inform but not trigger a consequential action. Our rule is
  weaker in what it forbids (memory may reorder and tighten) and stronger in what it assumes about the gate (the gate is a perceptual check,
  not a label lookup). "Corroboration-gated elevation" is the counterpart of our "fresh perception disposes".
* Weakens: **partial-strong for N2/N1 as applied to memory**; none for the physical gate and the mission-level evaluation. Read: full text
  retrieved; abstract, Sec. on the act gate and the theorems (partly).

**`karunanidhi2026utility`, `wei2025amemguard`.**
* Karunanidhi: plainly worded false assertions at 1.2 % of the corpus reduce LongMemEval accuracy from 0.850 to 0.300, and a four-stage content
  screening pipeline "refuses 0 of 360 poisoned memories"; argues the boundary of content-only screening is that telling a false assertion from a
  true one "generally requires external grounding beyond the text being screened". A-MemGuard: consensus-based validation across memories plus a
  "lessons" memory; reports over 95 % lower attack success.
* Relation: the first is direct support for our LLM-filter baseline failing on "poison-location" advice (a false but ordinary statement) and for
  grounding by perception at the station as the remedy. A-MemGuard is a filter/validation defence of the kind we compare against.
* Weakens: none (supports); A-MemGuard none-partial. Read: Karunanidhi abstract; A-MemGuard **abstract only**.

**`nguyen2026openbelief` (OpenBelief-Nav). Nguyen, D. T. et al. arXiv 2608.13923.**
* What it does: the selected 3D-scene-graph target "is treated as a hypothesis rather than a fixed semantic fact"; on arrival the robot verifies
  the candidate from RGB-D and, if verification fails, excludes it *for the current query only* and re-grounds over the remaining candidates "without
  modifying the persistent graph"; a 20-run pilot on a humanoid.
* Relation: this is "memory proposes, perception disposes" for navigation, including that memory is not rewritten by the failed check. It does
  not concern a safety bound, hazards, or repeated missions in changing worlds.
* Weakens: **partial-strong for the concept of N2** ("memory is a hypothesis verified on arrival"), none for the invariant/bound/evidence.
* Read: full text retrieved; abstract, Sec. 1, method.

**`zhang2026igvrrt`, `yin2026glove`, `tang2026vlmdewm`, `sun2026memorylies`.**
* IGV-RRT: scene-graph prior combined online with VLM relevance in changing environments (the prior can mislead: "prior bias"). GLOVE and
  VLM-DEWM: verify retrieved memory against fresh observations and realign it; DEWM validates a reasoning trace against the world model before
  execution. Sun and Zhang: an agent that trusts raw spatial memory dies more than twice as often as one with no memory (GPT-4o, FrozenLake).
* Relation: motivate the problem and the verify-before-act pattern; none states an invariant that memory can never remove a check.
* Weakens: **partial** (N2 mechanism). Read: abstracts (all four; texts retrieved but only abstracts read).

---

## 8. Verification before action, active perception and occlusion

**`oloo2026vaptamp` (VAP-TAMP). arXiv 2604.26988.**
* What it does: before and after each action a verify-execute-verify cycle asks a VLM several paraphrased yes/no questions, takes a majority
  vote, asks a view-sufficiency question and, if the view is insufficient, lets the VLM *suggest another viewpoint* until a viewpoint budget K is
  exhausted (Sec. IV-B1/B2, Alg. 2). A failed verification corrects the scene graph from the observation and triggers PDDL replanning. It states that
  prior systems "treat VLM outputs as infallible oracles".
* Relation: the closest published system to the whole N3+N4 pattern (VLM check before acting, repeated, with active view change). Differences: soft
  yes/no answers, majority vote and VLM-chosen viewpoints rather than closed-set next-token scores with permuted agreement and two fixed side poses
  used only to revoke; no independent velocity guard; no pre-registered audit; no memory.
* Weakens: **partial** (N3, N4; N2 via instance memory corrected by observation). Read: full text retrieved; Sec. I-II, III, IV-A/B, V partly.

**`hu2026oanbv` (OA-NBV). arXiv 2603.11072.**
* What it does: occlusion-aware next-best-view for mobile robots; the abstract opens "We naturally step sideways or lean to see around the
  obstacle when our view is blocked", motivated by disaster response; success above 90 % for seeing a partly occluded *person*.
* Relation: the same physical action as our look-around, with a principled viewpoint scoring, for people not hazards, and not tied to a decision gate.
* Weakens: **partial** (N3: novelty of side-stepping as such). Read: **abstract only**.

**`he2026detector`. He, Y. Detector confidence signals presence rather than occlusion. arXiv 2607.13361.**
* What it says: open-vocabulary detector confidence stays nearly constant while true visibility falls to one in eight; the detector "still reports
  the object present in 99 % of occluded frames"; this confidence is "widely read as a visibility signal... and gate active perception".
* Relation: independent support for N3's design choice of an *unconditional* look-around (we do not trigger it on low confidence). Not about VLM
  next-token scores, so the claim must be checked on our own data.
* Weakens: none (supports). Read: abstract only.

**`ren2024exploreuntil` (Explore until confident). RSS 2024.** Already in the bib; re-read abstract and introduction: builds a semantic map and
uses conformal prediction to calibrate the VLM's confidence "allowing the robot to know when to stop exploration". Relation: *confidence-triggered*
active perception; the alternative to our unconditional side views. **Partial** for N3. Abstract and Sec. 1 read.

---

## 9. Closed-set scoring, evaluation practice and pre-registration

**`ren2023knowno` (KnowNo). CoRL 2023 (arXiv 2307.01928).** Already in the bib; re-read relevant passages. The LLM generates options, the choice is formatted as
multiple-choice Q&A and the next-token likelihoods of the letters are the scores; conformal prediction calibrates a prediction set and the robot
asks for help when the set is not a singleton. In the appendix, after generating options they "append an additional option 'an option not listed
here'... and then randomize the order to further prevent bias", and note that GPT-3.5 shows "significant MCQA bias towards options D and E".
* Relation to N4: next-token scoring of a closed set and a randomised option order are already in KnowNo. What is ours: two permuted passes whose
  agreement is *required* (fail-closed conjunction), a separate hazard question, an independent velocity guard and the audited closed-loop evaluation.
  The claim "permuted options" must be worded as "agreement across two fixed permutations is required", not "we permute options".
* Weakens: **partial** (N4). Read: full text retrieved; Sec. 3-4 (passages above), Appendix prompts.

**`spitale2023reproducibility`. Spitale, M. et al. A systematic review on reproducibility in child-robot interaction. arXiv 2309.01822.**
* Sec. 3.4.2: "Only 3.38 % of the 296 manuscripts included in this survey reported that they pre-registered their works".
* Relation: supports the statement that pre-registration is rare in (human-)robot research. This review is about child-robot interaction (HRI),
  not mobile-robot navigation or manipulation; say "in HRI".
* Weakens: none (supports N4's methodological claim). Read: full text retrieved; Sec. 3.4.2.

**Not found.** We found no robotics paper that pre-registers closed-loop trials with simulator-ground-truth audits, and none that makes a
prediction of closed-loop mission behaviour from a component model before the test (study V). The nearest practices are statistical-rigour
guidance for robot evaluation (`snyder2025policycomparison`, `kressgazit2024empirical`, already cited) and sim-to-real correlation studies
(`li2024simpler`). Absence of evidence in a US-only, arXiv-heavy search is weak; word the claim "to our knowledge".

---

## 10. Classical foundations (bibliographic verification only; not re-read)

These are the sources a security or control reviewer will have in mind. Cite them in one sentence in the paper.
* `biba1977integrity`: the integrity model "no read down / no write up": low-integrity data must not influence high-integrity objects. (MITRE
  report; no DOI.) The oldest statement of N1's principle.
* `denning1976lattice`: lattice model of information flow; `sabelfeld2003language`: survey of language-based IFC including non-interference and
  declassification/endorsement. Fides builds on these.
* `saltzer1975protection`: the principles of *fail-safe defaults* and *least privilege*; "fail closed" in N4 is fail-safe defaults.
* `birgisson2014macaroons`: bearer credentials whose caveats can only *restrict* ("attenuate") what the holder may do; anyone, including an
  untrusted party, can add caveats, and none can remove one. This is the closest *mechanical* precedent for "advice may only tighten".
* `ramadge1987supervisory`: supervisory control: the supervisor can only disable controllable events. Together with shields
  (`alshiekh2018shielding`) this is the formal-methods precedent for a layer that can only remove permissions.

---

## 11. Threats to our novelty (ranked)

**1. N1 is non-interference / attenuation under a new name, and the Proposition is a by-construction fact (Fides, Biba/Denning, macaroons, supervisory control).**
Why it bites: the lead contribution is a security principle, and Fides states and enforces its stricter form for LLM agents; "approvals with advice
are a subset of approvals without advice" is one line once the interface has no field that can relax a check (we say "elementary by design"
ourselves). A security reviewer will call it trivial and old.
Suggested wording change:
* Do not present the principle as new. Say: "We instantiate a one-sided relaxation of integrity non-interference (Biba, Fides): advice may influence
  *where* the robot looks first and *how cautiously* it decides, but not *whether* it checks. This keeps the benefit of correct advice, which strict
  non-interference throws away."
* Call Prop. 2 an "observation" or "proposition by construction" and put the weight on (i) the typed interface and its enforcement plus audit,
  (ii) the probabilistic bound k*eps for a perceptual check, (iii) the measured availability cost, (iv) the audited closed-loop comparison.
* State that strict IFC on this system equals the no-advice arm (study A control), so "ignore all advice" is already a baseline.
Extra checks (cheap, offline from existing ledgers): report advice-induced *exposure* (how often a misleading location hint sends the robot first to
the station with a fire; the guarantee is about delivery, not travel) and put it in the cost bound.

**2. The algorithms-with-predictions framing makes N1 look like a standard consistency/robustness result with robustness = 1 (Dinitz, Lykouris and Vassilvitskii, Li et al., MetaBSG).**
Why it bites: a theory reviewer will say "predictions used only for ordering never affect correctness" is textbook, and a robotics reviewer will point to
MetaBSG ("untrustworthy commands... guarantees even when arbitrarily bad").
Suggested wording: embrace the frame. "In the language of algorithms with predictions, advice is 1-robust for safety by construction and (1+delta)-robust
for time (at most one wasted visit per station), and consistent in time when truthful." Cite Lykouris and Vassilvitskii, Purohit et al., Dinitz et al., Li et al.,
Xu et al.; say what differs: the protected quantity is a probabilistic perceptual check and a physical delivery, and the adversary is part of the evaluation.
Extra experiment: a consistency-robustness curve for study A, sweeping the *fraction of truthful advice* (0, 25, 50, 75, 100 %) and plotting time
saved (consistency) against time lost and refusals (robustness) for monotone, naive and filter arms. Add one *learned-trust* arm after
`asmar2025learning` (Bayesian suggester reliability) to answer "why not simply learn how much to trust the advisor"; expect it to match monotone on safety only
if the adversary is not adaptive, which is the point to demonstrate.

**3. N2 "memory proposes, perception disposes" is already how navigation memories with arrival verification work (OpenBelief-Nav, GLOVE, VLM-DEWM, IGV-RRT), and RoboSafe's memory only adds blocking predicates.**
Why it bites: "check-preserving memory" can be read as "memory with verification", which exists; the pre-action VLM gate and delivery setting are a
setting change.
Suggested wording: claim the *invariant and its consequences*, not the pattern. "Prior memories treat remembered targets as hypotheses to be verified on
arrival; we make it an invariant (no input can lower a threshold or drop a view), prove the bound k*eps for any visiting order, recompute it in the audit, and
show in changing worlds that a memory that skips checks is unsafe (campaigns H and V)." Avoid "first".
Extra experiment: add the read-time filter of `sun2026memorylies` or an OpenBelief-style "verify with a single pass, then trust" arm to campaign H or V if
compute permits; if not, say plainly that it was not run.

**4. N3 look-around is classical active perception / next-best-view (Bajcsy, VAP-TAMP's VLM-chosen viewpoints, OA-NBV's literal "step sideways", Explore-Until-Confident).**
Why it bites: two fixed side steps look like a naive NBV, and a reviewer can ask for a comparison with a confidence- or VLM-triggered view.
Suggested wording: present it as an *empirically validated safety fix with revoke-only semantics*, not as a perception method: "Rather than choose
views by uncertainty (VLM confidence does not flag occlusion), we always take two cheap side views, and they can only revoke an approval." Credit OA-NBV and
VAP-TAMP; cite `he2026detector` as independent evidence that detector confidence is not an occlusion signal, and test the claim on our own data.
Extra analysis (offline, no new rollouts): on the study W data, report how well the front-view VLM score predicts a miss (AUROC of p_h or its entropy for
"fire visible only from the side"). If it is near chance, a confidence-triggered look would not have fired; that answers the objection with data.

**5. Scene text (study S) can be neutralised by a cheap OCR mask (Samarakoon et al.: 0 successes in 5,400 trials), and concurrent work is converging on provenance-aware privilege (Chang et al., the 2026 embodied-security survey).**
Why it bites: our admission that scene text is outside the guarantee is honest, but a baseline with zero attack success exists in the literature; and the survey
(Aug 2026) names provenance-aware privilege control as the next step, so N1 may be preempted before camera-ready.
Suggested wording: "Scene text enters through perception and no structural argument covers it. Text masking removes attacks that rely on text, at the price of
legitimate labels and of non-text attacks (decals, fake items); we measure the residual." Mark all novelty statements "to our knowledge, as of October 2026".
Extra experiment: add a text-mask arm (OCR masking) and an "ignore scene text" prompt arm to study S, with a benign-label control to measure the utility
loss; consider posting the preprint early to timestamp N1.

*Lesser risk (N4).* Each part of N4 is known: letter scoring and randomised options (KnowNo), a separate safe layer (Simplex, shields, SafeTap), pre-registration (open
science). Word the contribution as a *combination plus an auditable evaluation*, and state "agreement across two permutations is required" instead of "options are permuted".

---

## 12. Positioning statement (paste-ready)

> Defences against prompt injection for LLM agents keep untrusted data away from consequential decisions, by separating control from data flow or by tracking
> integrity labels (CaMeL, Fides); algorithms with predictions let untrusted advice reduce cost without ever changing correctness or the worst-case bound
> (Lykouris and Vassilvitskii; Dinitz et al.); and runtime assurance keeps a trusted decision module between an untrusted advanced component and the actuators
> (Simplex, shields). We bring these ideas to a physical pre-action gate that is itself a probabilistic perception check. Every input the robot did not perceive
> at the station (memory, a peer's report, the inventory, the operator's wording) is typed as advice, which may only reorder visits or tighten thresholds, never
> remove a check. Unlike strict non-interference, correct advice still saves time; unlike filters and guardrails, the guarantee does not depend on recognising advice
> as malicious. The per-mission probability of an unsafe delivery under any advice, even adversarial, is therefore bounded by the advice-free bound (k times the
> per-check false-approval rate), and the availability an attacker can buy is bounded by one wasted visit per station plus the per-view false-alarm rate. To our
> knowledge, as of October 2026, no prior work gives this typed interface, bound and a ground-truth-audited closed-loop comparison against naive and filter baselines
> for a VLM-gated delivery robot; text written in the scene reaches the decision as perception and remains outside the guarantee, which we measure rather than claim.

---

## 13. Limits of this survey

* Search was by web search (US-only index) and arXiv full text; ACM, IEEE Xplore and Springer pages were not read. Venue and page data came from Crossref,
  PMLR/NeurIPS/AAAI/KR proceedings pages and the arXiv API. Several 2026 preprints have no venue; they are cited as preprints.
* An ICML 2026 poster on persistent "cognitive pathogens" (memory poisoning of zero-shot object-navigation agents, "VIRUS") appeared in a search listing; no arXiv
  or proceedings text was found, so it is not cited. An arXiv paper on memory-poisoning detection (2609.08747, MemSentry) was retrieved but not read, and is not cited.
* Several works are single-author or very recent preprints (TMA-NM, Karunanidhi, He, Liu et al.); their claims are the authors' own and unreplicated.
* "Weakens" ratings are our judgement. We tried to rate against the strongest reading a hostile reviewer could give.
