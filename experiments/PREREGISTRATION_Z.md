# Pre-registration — study Z (non-generative zero-shot baselines), fixed before any baseline inference

**Question.** Is a generative VLM needed at all? A simulated reviewer argued that a contrastive image–text model
(CLIP-style), with the same decision structure, might also verify the supply and spot fires. Study Z executes that
baseline on the same held-out images as our system, with thresholds chosen only on development data.

**Baselines** (`scripts/zeroshot_baseline.py`). Both are open checkpoints from Hugging Face:
* **Z1:** SigLIP `google/siglip-so400m-patch14-384`.
* **Z2:** CLIP `openai/clip-vit-large-patch14`.

**Prompts** are fixed in the script before any scoring.
* Supply: softmax over three prompts:
  * "a pack of plastic water bottles on a grey platform";
  * "a white first-aid kit with a red cross on a grey platform";
  * "an empty grey platform or some other object".
* Hazard: a 2-way softmax over "fire, flames or smoke" vs "no fire and no smoke". It is computed on the full image and
  on the same three enlarged crops our v3.6 system uses, and the maximum is taken.
* Approve iff:
  * the arg-max supply is the requested one;
  * its probability is ≥ τ_s;
  * the hazard probability is < τ_h.

  This is the structure of our Eq. 1, without the second permuted question, which has no analogue here.

**Threshold selection (development data only).** Use the development images v1 + v2 + DH + DH2 with the expected
decisions of `scripts/i13_select.py`. Over the grid τ_s ∈ {0.34, 0.40, …, 0.94} × τ_h ∈ {0.05, 0.10, …, 0.95}:
1. Among pairs with the fewest development false approvals, choose the one with the most correct approvals.
2. Break ties by the lower τ_h.

The chosen pair is written to `experiments/results/z_thresholds.json` before T1 or T2 is scored.

**Evaluation.** Held-out T1 (600 images, non-ambiguous) and T2 (600 images), the same images and labels as before.
* Report false approvals (must-refuse approved) and correct approvals, with Wilson CIs, for Z1 and Z2.
* Compare with our registered system on the same images:
  * T1: Qwen3.5-9B v3.5 rule, `devset_t1_qwen35_9b.json` at τ_h 0.05;
  * T2: v3.6 `Q9B[h36_tiles]`.
* Paired exact McNemar tests on (a) must-refuse images and (b) must-approve images.

**Claim rule.**
* "The VLM check is safer than the zero-shot baseline": fewer false approvals with p < 0.05 on T1 or T2, and correct
  approvals not lower with p < 0.05.
* "More available": more correct approvals with p < 0.05, and false approvals not higher with p < 0.05.
* Otherwise the counts are reported as "no significant difference".

## Amendments
(none)
