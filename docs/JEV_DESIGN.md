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
