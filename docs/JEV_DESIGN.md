# Jev: a heterogeneous judge that may only veto (design, 2026-10-21; idea: the user)

**Idea.** RescueMind's gate has one VLM (Qwen3.5-9B). Its errors (small, partly hidden fires scored 0.008-0.024, inside the clean tail) are the largest remaining weakness (14/136 closed-loop, upper 15.6%).
A second judge from a *different model family* ("Jev": other vision encoder, other language backbone, other training data) is asked the same safety question; the robot proceeds only if **both** pass. Like advice, Jev can only
tighten: it never approves what the primary refuses (so Prop. 2 still holds, and the budget of the conjunction is at most the smaller of the two single budgets, whatever the correlation).
The empirical question is how much *smaller*: independence would multiply the misses, a shared failure (the same hidden fire) would not.
The 2-AI idea was tried once with Clef-Flash (study J, 23/24 vs 24/24), but Clef-Flash is a fine-tune of Qwen3.5-9B, so the failures were correlated by construction and the test said nothing about diversity.

**Three places, increasing ambition.**
1. *Station check (image level, GPU only).* Judges: Qwen3.5-9B (existing scores), InternVL3-8B-hf (Qwen2.5 LM + InternViT), Idefics3-8B-Llama3 (Llama 3.1 + SigLIP), Qwen3-VL-8B (same family, newer), SmolVLM2-2.2B (small). Same hazard question (h36 wording, tiles), next-token Yes/No score.
   Per judge: threshold from the rank rule at alpha = 2% on the clean views; joint miss of the conjunction on the perceivable-fire views, against the product of the single misses (the independence line); union false-stop rate (the availability price); AUC per judge.
2. *Driving judge (closed loop).* The velocity guard sees geometry (lidar), not fire or smoke on the route. Before each leg the judge looks at the front camera and may veto ("is fire, smoke or a person on the path ahead?"); a veto stops and re-plans (or reports). Test: depot worlds with a fire/smoke bank across an aisle between stations.
3. *Disagreement as a trigger.* When the two judges disagree the robot takes the look-around (active perception) instead of refusing outright; compare refusals, misses and time with always-look and never-look.

**What would count as a result.** A measured error correlation across families (not assumed), a conjunction that lowers the missed-fire rate at a stated availability price, a route-hazard case that the lidar guard alone cannot handle, and a comparison with the published VLM-monitoring work (Sentinel, FAIL-Detect, Code-as-Monitor, VAP-TAMP, KnowNo) in the related-work table of the paper.

## Speed is Jev's strength (user, 2026-10-22): the cascade
The gate's accuracy cost is time: Qwen3.5-9B scores a station with four passes (full image + three crops), about 2-6 s per checkpoint (`vlm_latency_s` in the ledgers); a Jev-class judge answers in one forward pass (Clef-Flash 0.6 s per image, T2). Three uses that make the speed count:
1. **Driving judge (the natural home of speed).** A per-leg veto must run while the robot moves; Qwen is too slow for it, a fast judge is not. The judge only vetoes (stop and report); the lidar guard still owns the wheels.
2. **Early exit at the station.** Because the rule is a conjunction, the order does not change the decision: the fast judge looks first; if it flags, the robot refuses at once (no Qwen call, a refusal is seconds faster); if it passes, Qwen decides. Accuracy is that of the conjunction, mean time is lower on refusals.
3. **Disagreement triggers the look-around.** If the fast judge flags but Qwen does not (or the reverse), take the side view instead of refusing at once: the slow, accurate look is spent only where the two disagree.
Measured per judge in study JH from now on: `latency_s` per image (four passes) in `jev_scores_*.jsonl` (additive field; rows scored before this note lack it). Code: `scripts/local_vlm_server.py --judge NAME --judge-threshold TAU` (the judge's score is put on the gate's scale, effective hazard = max(p_qwen, p_judge x tau_h / tau_judge): a veto, never an approval), `scripts/v32_orchestrate.py --judge ... --judge-threshold ...`; `tests/test_judge_veto.py`.

## Result of study JH (2026-10-22, `experiments/results/jh_summary.json`)
XD test split (126 perceivable fires, 104 clean twins), threshold of each judge by the rank rule at alpha = 2% on the clean calibration worlds, Qwen3.5-9B alone misses 14.

| judge | cal AUC | joint miss (union) | phi with Qwen | false stops (union, of 104) |
|---|---|---|---|---|
| InternVL3-8B (selected) | 0.976 | 10 | 0.41 | 0 |
| Idefics3-8B | 0.933 | 8 | 0.30 | 1 |
| SmolVLM2-2.2B | 0.954 | 9 | 0.42 | 4 |
| Qwen3-VL-8B | 0.958 | 14 | 0.75 | 0 |

**JH1 fails** for the judge selected by the registered rule (10 > floor(2 x 14 / 3) = 9); it is a failed claim. What survives (descriptive): the veto lowers the miss by 29-43% at 0-1 extra false stops, the same-family judge adds nothing (every miss shared), and the misses of other families still overlap with Qwen's (phi 0.3-0.4, about three times the overlap that independence would give). Small, partly hidden fires are hard for every model tested; a second judge is a modest extra layer, not a way to the zero-miss budget.
