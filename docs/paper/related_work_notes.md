# Related-work notes (verified bibliography)

Companion to `references.bib`. All 44 entries were checked on 2026-10-16 against a primary
source: the arXiv API/abstract page, PMLR / NeurIPS / ICLR / ACL proceedings pages, OpenReview,
Crossref DOI metadata (the publisher record), JMLR, or the official Hugging Face model card.
Keys below match `references.bib`.

Shorthand for our system: **closed-set log-prob checkpoint** (MCQ answer-letter next-token
probabilities, 2 permuted questions plus a Yes/No hazard question), **fail-closed** (approve only
if both agree and the confidence clears a threshold), **recovery search** (wrong item leads to
the other station), **hazard stop**, an **independent velocity guard** (sole publisher of wheel commands),
a **ground-truth audit** (Gazebo), and a **pre-registered** evaluation.

## 1. Failure detection, explanation and self-verification with LLMs/VLMs

- **liu2023reflect**: REFLECT (CoRL 2023) turns multisensory robot logs into a hierarchical text summary and asks an LLM to explain failures and replan. It works after the fact and produces free-form text. Our check runs *before* acting, uses closed-set scoring, and its decision is a bounded accept/reject.
- **duan2025aha**: AHA (ICLR 2025) fine-tunes a VLM on procedurally generated failures (FailGen) to detect and explain manipulation failures in natural language. It shows that VLMs can verify task outcomes. We use an off-the-shelf local VLM without fine-tuning and constrain it to multiple-choice letters, so the output can be thresholded and audited.
- **huang2023innermonologue**: Inner Monologue (CoRL 2022, PMLR 2023) feeds success detection and scene descriptions back into an LLM planner as closed-loop language feedback. Our feedback is likewise used for recovery (searching the other station), but the gate is a calibrated reject option, not an open-ended prompt.
- **ichter2023saycan**: SayCan (CoRL 2022) combines LLM token likelihoods over a *fixed set of skills* with value-function affordances. It is a close precedent for scoring a closed candidate set by LM likelihood, which is the same principle as our letter-probability scoring, but SayCan applies it to planning rather than verification. *Note:* PMLR lists brian ichter first, while arXiv lists Michael Ahn first ("Ahn et al."). Pick one form and use it consistently.
- **ren2023knowno**: KnowNo (CoRL 2023) frames LLM planning as multiple-choice next-token scoring and uses conformal prediction to decide when the robot should ask for help. This is the closest methodological relative of our work. We share MCQ token-probability scoring and abstention, but our response to uncertainty is to fail closed or search, not to ask a human. We also add permutation-agreement and do not claim a conformal coverage guarantee.
- **du2023successdetectors**: Du et al. (CoLLAs 2023) fine-tune a VLM (Flamingo) as a success detector framed as visual question answering. Our item check is also a VQA-style success/identity check, but zero-shot, closed-set, and audited against simulator ground truth.
- **agia2025sentinel**: Sentinel (CoRL 2024, PMLR 2025) monitors generative policies at runtime. It pairs a temporal-consistency detector for erratic failures with a VLM that judges task progress. It is a runtime monitor for a learned *policy*, whereas we monitor a perception decision and keep motion safety in a separate guard.
- **xu2025faildetect**: FAIL-Detect (RSS 2025) detects imitation-policy failures without failure data, using uncertainty scores and conformal thresholds. It is related in spirit, because the threshold is chosen for a target false-alarm level. Our threshold is pre-registered and evaluated against ground truth.
- **zhou2025codeasmonitor**: Code-as-Monitor (CVPR 2025) has a VLM write constraint-checking code for reactive and proactive failure detection. It is an alternative to our design: it turns monitoring into programs, while we turn it into scored MCQs.
- **liang2024introspective**: Introspective Planning (NeurIPS 2024) has LLM planners retrieve introspective reasoning examples to align their uncertainty with real task ambiguity, and combines this with conformal prediction. It includes a mobile-manipulation benchmark and is related to our goal of approving only when the model is confidently and consistently right.

## 2. Multiple-choice answering with LLMs and its biases

- **robinson2023mcqa**: Robinson et al. (ICLR 2023) show that presenting the options together and scoring the *answer symbol* ("multiple-choice prompting") works well when a model has good "multiple choice symbol binding". This is the direct basis for our letter-probability scoring.
- **zheng2024mcselectors**: Zheng et al. (ICLR 2024) show that LLMs have a "selection bias" toward particular option IDs, caused mainly by token-prior bias, and propose PriDe, which debiases by permuting options. This motivates our two permuted questions plus an agreement requirement, which is a cheap test-time defence against letter bias.
- **pezeshkpour2024order**: Pezeshkpour & Hruschka (Findings of NAACL 2024) document large accuracy swings when the order of options is changed. This is further justification for asking the question twice with the options permuted.
- **kadavath2022know**: Kadavath et al. (arXiv 2022) find that large LMs are fairly well calibrated on well-formatted multiple-choice questions and can estimate P(True). This supports using answer-token probabilities as confidence. Our threshold and audit test whether this holds for a 9B VLM on images.
- **guo2017calibration**: Guo et al. (ICML 2017) show that modern deep networks are overconfident and that temperature scaling helps. It is the standard reference when arguing that raw softmax confidence needs validation before it is used as a threshold.
- **zhao2021calibrate**: Calibrate Before Use (ICML 2021) shows that LM predictions are biased by prompt format, label order and majority labels, and proposes contextual calibration. It is complementary evidence that letter probabilities are biased, and an alternative to our permute-and-agree design. *Note:* PMLR spells the first author "Zihao Zhao", while arXiv uses "Tony Z. Zhao".
- **wang2023selfconsistency**: Self-Consistency (ICLR 2023) samples several reasoning paths and takes the majority answer. Our two-question agreement is a deterministic, minimal form of consistency checking. It perturbs the prompt instead of sampling.
- **li2023pope**: POPE (EMNLP 2023) evaluates object hallucination in VLMs with Yes/No polling questions. It is relevant to our Yes/No hazard question and to the risk that a VLM confirms an item that is not present.

## 3. Selective prediction / reject option

- **geifman2017selective**: Geifman & El-Yaniv (NIPS 2017) build a selective classifier on top of a trained network by thresholding confidence to guarantee a target risk with high probability. Our fail-closed rule is a selective classifier, so we should report risk–coverage (wrong approvals versus abstentions) in these terms.
- **elyaniv2010selective**: El-Yaniv & Wiener (JMLR 2010) give the theoretical foundations of selective classification and the risk–coverage trade-off. It is the canonical citation for the reject-option framing.
- **angelopoulos2021conformal**: Angelopoulos & Bates (arXiv 2021) is a tutorial on conformal prediction and distribution-free uncertainty quantification. It is useful for contrasting our pre-registered fixed threshold with calibration-set conformal thresholds such as those used by KnowNo and FAIL-Detect.

## 4. Statistics, evaluation practice, pre-registration

- **wilson1927probable**: Wilson (JASA 1927) introduces the score interval for a binomial proportion. We use it for the confidence intervals on success and false-approval rates.
- **mcnemar1947note**: McNemar (Psychometrika 1947) gives a test for the difference between correlated (paired) proportions. We use it for paired comparisons of conditions on the same trials or images.
- **kressgazit2024empirical**: Kress-Gazit et al. (arXiv 2024) recommend reporting experimental conditions, using several metrics, doing statistical analysis and describing failure modes when evaluating robot policies. Our ground-truth audit and pre-registration follow these recommendations. It is still an arXiv preprint; no peer-reviewed venue was found.
- **nosek2018preregistration**: Nosek et al. (PNAS 2018) is the canonical argument for pre-registration, which separates confirmatory from exploratory analysis. We cite it to justify registering the held-out test set and the analysis plan before rendering or running.
- **hofman2023preregistration**: Hofman et al. (arXiv 2023) propose pre-registration specifically for predictive modelling in ML. It is the closest ML-specific precedent for our pre-registered checkpoint evaluation.

## 5. Safety architecture

- **seto1998simplex**: Seto et al. (ACC 1998) introduce the Simplex architecture, in which a verified safety controller monitors a complex or untrusted controller and can override it. Our independent velocity guard, the only node allowed to publish wheel commands, is a Simplex-style decomposition: the VLM never touches actuation.
- **sha2001simplicity**: Sha (IEEE Software 2001) argues that a simple, reliable core component that ensures the critical functions matters more than design diversity. It is the conceptual justification for keeping the guard small and independent of the VLM.
- **alshiekh2018shielding**: Alshiekh et al. (AAAI 2018) synthesise a "shield" from a temporal-logic specification that corrects unsafe actions of an RL agent at runtime. It is analogous to our velocity guard, but our guard is hand-written and does not provide a formal-synthesis guarantee.
- **ames2019cbf**: Ames et al. (ECC 2019) survey control barrier functions as safety filters around arbitrary controllers. It is an alternative, formal way to build the guard, and worth citing as future work.
- **robey2025jailbreaking**: Robey et al. (ICRA 2025) show that LLM-controlled robots can be jailbroken into harmful physical actions. This motivates not letting the language/vision model publish actuation commands directly.
- **ravichandran2026guardrails**: RoboGuard (IEEE RA-L 2026; arXiv 2025) is a guardrail architecture that checks LLM-generated robot plans against safety rules before execution. It is related to our layered design, but works at the plan level, whereas our guard works at the velocity-command level.

## 6. Disaster robotics and humanitarian logistics

- **murphy2014disaster**: Murphy (MIT Press 2014) is the reference monograph on robots deployed at real disasters and how they fail. It is useful for motivating conservative, fail-safe behaviour and human-trust requirements.
- **delmerico2019rescue**: Delmerico et al. (J. Field Robotics 2019) survey the state and outlook of rescue robotics across platforms. It positions our work as a logistics/delivery task rather than search and rescue.
- **balcik2008lastmile**: Balcik, Beamon & Smilowitz (J. Intelligent Transportation Systems 2008) define last-mile relief distribution from local depots to beneficiaries. This is the operations-research framing for our station-to-recipient delivery.

## 7. Tooling and models

- **macenski2022ros2**: Macenski et al. (Science Robotics 2022) describe the design and architecture of ROS 2, our middleware (Jazzy).
- **koenig2004gazebo**: Koenig & Howard (IROS 2004) is the original Gazebo paper. We use Gazebo Harmonic, a successor version, as the simulator and the ground-truth source for auditing.
- **tobin2017domain**: Tobin et al. (IROS 2017) introduce domain randomization for sim-to-real perception. It is relevant to our held-out test set, which varies lighting, prop placement and distractors, although we use the variation for *evaluation*, not training.
- **bai2025qwen25vl**: The Qwen2.5-VL technical report (arXiv 2025) is cited as the predecessor model family and for the vision-language architecture lineage.
- **bai2025qwen3vl**: The Qwen3-VL technical report (arXiv 2025) is the immediate predecessor of Qwen3.5's vision capability. The Qwen3.5 model card states that Qwen3.5 outperforms Qwen3-VL.
- **qwen2026qwen35**: Qwen3.5 (Qwen Team, February 2026) is the model we run locally (Qwen3.5-9B, image-text-to-text). The citation form, title "Qwen3.5: Towards Native Multimodal Agents", month and year are copied from the BibTeX in the official model card, and its license is Apache-2.0 (from the model-card metadata). Hugging Face shows that the first Qwen3.5 repository (397B-A17B) was created on 2026-02-16 and the 9B repository on 2026-02-27; the exact public announcement day is not confirmed (see below).

## 8. VLMs / VLAs for embodied and mobile robots

- **zitkovich2023rt2**: RT-2 (CoRL 2023) co-fine-tunes web-scale VLMs to output robot actions as tokens (a vision-language-action, or VLA, model). It is the opposite design choice to ours: the VLM *acts*, while ours only *verifies* and never commands motion. *Note:* PMLR lists Brianna Zitkovich first, while arXiv lists Anthony Brohan first ("Brohan et al.").
- **kim2025openvla**: OpenVLA (CoRL 2024, PMLR 2025) is an open-source 7B VLA trained on Open X-Embodiment. It is representative of end-to-end VLM control, which we deliberately avoid for safety-critical motion.
- **huang2023vlmaps**: VLMaps (ICRA 2023) fuses visual-language features into a 3D map for language-conditioned navigation. It is a representative VLM-for-mobile-robots work, but it uses VLMs for spatial grounding rather than for verifying an item before handover.

## UNVERIFIED / not included

All named candidates were found and verified. Only the items below were not confirmed, and none of them is a separate .bib entry:

1. **Exact public release day of Qwen3.5.** The official blog (`qwen.ai/blog?id=qwen3.5`) renders with JavaScript and returned no content when fetched, so its date could not be read. "February 2026" comes from the official model-card BibTeX. Third-party sites disagree (24 Feb versus 2 Mar 2026) and were not used. The entry keeps only the month and year.
2. **Qwen3.5 technical report.** No arXiv technical report for the base Qwen3.5 family was found. The only hit was "Qwen3.5-Omni Technical Report" (arXiv 2604.15804), which is a different model, so cite the blog/model card instead.
3. **A peer-reviewed venue for Kress-Gazit et al. 2024.** Only the arXiv version was found, and DBLP lists only CoRR. It is included as `@misc` (arXiv), not as a journal or conference paper.
4. **NeurIPS 2020/2021 "pre-registration experiment" workshops.** The workshop pages exist on neurips.cc, but they are workshop listings rather than a single citable paper, so they were left out. Cite Hofman et al. 2023 or Nosek et al. 2018 instead.
5. **VLM-specific calibration paper.** The brief asked broadly for "calibration of LLMs/VLMs". No specific VLM-calibration paper was verified, so this is covered with Guo 2017, Zhao 2021 and Kadavath 2022, plus POPE for VLM Yes/No reliability.

Year conventions: PMLR dates CoRL 2022 (v205) as 2023 and CoRL 2024 (v270) as 2025. The .bib follows PMLR and adds a `note` with the conference year.
