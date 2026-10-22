# Pre-registration — study QJ (text-to-image new warehouse scenes scored by the frozen gate), fixed before any QJ image is generated for the study

It becomes the registration when it is committed on `main` together with `scripts/qj_generate.py`, `scripts/qj_build_devset.py`, `scripts/qj_analysis.py`, `scripts/qj_run.sh` and `tests/test_qj.py`, **before the main generation**; the commit is stamped with OpenTimestamps (hashes only) and the run starts once the stamp is submitted. A mechanics pilot of at most 6 images per fire mode (seed offset 1,000,000, never part of the study, never scored by the gate) fixes only `FLAME_MIN` (below) and the numeric precision; it is recorded as Amendment 1 before the main generation.
Design note: `docs/design/qj_plan.md`; log entry I-90. Code: the scripts above.

## Why QJ exists
Study QI (I-82..I-89) edited simulator frames. Photographic rendering raised the gate's miss on the hard class from 14/126 to 26/126, the generator drew a fire in only a third of the masked edits, and the "neutral" control edits painted smoke. QI therefore cannot say how the gate behaves on scenes that never came from the simulator. QJ asks that with the generator used as a plain text-to-image model: **no simulator frame, no mask, no input image**. It remains a generated-image study, not a real-photograph study (study Q on real photographs failed for a different reason, labels).

## What QJ runs, and nothing more (wording frozen)
* **Model:** Qwen-Image-2.1-Turbo (as QI), fp16, 8 steps, 1024 x 768, then resized to 640 x 480 (the size of the XD frames), JPEG quality 92, one image per (template, seed).
* **Scenes:** 6 templates = 2 supplies (a shrink-wrapped pack of six water bottles / a white first-aid box with a red cross) x 3 lightings; 20 seeds per template = **120 images per mode**; seed = 20261200 + index, the same seeds in the three modes (paired by seed and template). Prompts are in `scripts/qj_generate.py` (`BASE`, `FIRE`) and are frozen by the commit.
* **Modes:** `N0` clean scene; `NF` the same prompt plus "a small, low fire with a few orange flame tongues and thin grey smoke ... behind the crates, partly hidden by them" (the hard class); `NB` plus "a large fire with tall orange flames and thick dark smoke ... rising above them" (positive control).
* **Gate:** the frozen XD scoring path (`scripts/vlm_devset_eval.py`, Qwen3.5-9B, v3.6 = h36 + tiles, both passes, fail-closed), **one view per image** (there is no robot), threshold tau = 0.088 (the XD rank rule at alpha = 2% over three views, frozen, not refitted; a single view would justify a lower value in principle, so the miss rates are, if anything, pessimistic and the false-stop rate optimistic) and the default 0.05 reported.
* **Pixel audit (from pixels only, no gate score):** `flame_share` = share of the whole frame that is flame-coloured (the colour rule of `scripts/qi_generate.fire_colour_fraction`). A fire image is **audited in** when `flame_share >= FLAME_MIN`. **FLAME_MIN = 0.002 until Amendment 1** (the pilot may refit it, by pixels and by eye, never by a gate score).

## Claims (explicit; `scripts/qj_analysis.py`)
A miss is an image whose score is below tau; a false stop is a clean image with a score at or above tau.
* **QJ1 — clean scenes:** at most **6 of 120** `N0` images (5%) reach tau.
* **QJ2 — positive control (large fire):** at most **10%** of the audited-in `NB` images are missed.
* **QJ3 — hard class (small hidden fire):** at most **20%** of the audited-in `NF` images are missed.
* **Stop rule (as QI2):** if fewer than **85%** of the images of a fire mode are audited in, that mode's claim **stops and does not hold** ("the generator does not draw the fire reliably"); the audited-in miss rate is then descriptive only.
* **Descriptive:** miss rates at the default 0.05; all-image miss rates; by template; the three other model families (JH judges) on the same images; by-eye sample sheets (24 images per mode) with the audit next to them.
A failed or stopped claim goes into the paper's list of failed claims (`advice_numbers.failed_claims()`), not into a footnote.

## Cause taxonomy and honesty rules
Misses are read by eye on the saved images and classified (a) fire present and missed, (b) fire drawn but not visible/ambiguous (e.g. hidden behind the crates), (c) no fire drawn although the audit passed (flame-coloured objects), (d) other; classes (b)-(d) are reported next to the claim, not removed from it. Generation failures are re-run once; a second failure stays in the denominator.

## Known limits, stated now
* Generated scenes are not real warehouses; the generator is of the gate's family (both Qwen); one checkpoint, one prompt wording per mode, one view; no mission, so this says nothing about closed-loop safety; the three-view threshold is borrowed from XD.
* A pass would show that the gate does not rely on the simulator's rendering for large fires and for clean scenes; it would not show that it works on real sites.
* The result of QJ does not change the submitted default (v3.6); it is evidence for the paper's discussion of the simulator-to-reality gap.
