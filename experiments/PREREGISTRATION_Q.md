# Pre-registration — study Q (does the supply check transfer to real photographs?), fixed before any Q inference

**Motivation.** Every image the supply check has seen so far was rendered by Gazebo: a grey platform with a stylised
water pack or first-aid box. Studies P and P2 tested the *hazard* question on real photographs (D-Fire). Study Q tests
the other half of the checkpoint, the **supply check**, on real photographs. The hazard question is **not** evaluated
here; P and P2 cover it.

**System under test.** The frozen v3.6 supply check: Qwen3.5-9B, prompt set `v35`, the two option-permuted closed-set
questions (`scripts/local_vlm_server.py`, `PROMPT_SETS['v35']['supply']`), decision rule of
`rescuemind/local_vision.py` / `scripts/i13_select.py::q_allows`: **approve iff, in both passes, the arg-max supply is the
requested one and its closed-set probability is ≥ τ_s = 0.5.** A pass that returns an error is a refusal. The hazard
term of Eq. 1 is dropped (no platform, no fire here). No prompt, threshold or code path is changed on the basis of Q.
The server is started as `--model Qwen/Qwen3.5-9B --prompt-set v35` (its hazard settings do not affect the supply
probabilities).

## Data and licences
* **Source:** Wikimedia Commons (`commons.wikimedia.org`), queried through the public API by `scripts/q_fetch.py`. We
  first checked Open Images V7: its validation split has 0 images labelled "First aid kit" and 13 "Bottled water", too few.
* **Per-image licence** is read from the file page's `extmetadata` (`LicenseShortName`, `LicenseUrl`, `Artist`) and
  recorded with the file-page URL and the sha256 of the downloaded file in `experiments/q_sample.json`. Licence policy,
  fixed before any download: `^(CC0|CC BY x.y|CC BY-SA x.y|Public domain)`; NC, ND, GFDL-only and unknown licences are
  excluded. In the final sample: CC BY-SA 4.0 ×153, CC BY-SA 3.0 ×78, CC BY 4.0 ×46, CC BY 2.0 ×42, CC0 ×40, Public
  domain ×24, and 22 CC BY / CC BY-SA 2.0–3.0 / 2.5 images.
* **Redistribution:** the images themselves are **not** committed (they stay in `~/.cache/rescuemind/q/images`, 960-px
  Commons thumbnails, 214 MB). The repository holds only title, file-page URL, author, licence and sha256, which is the
  attribution CC BY and CC BY-SA ask for. Anyone can refetch the files with `scripts/q_fetch.py --all`.
* **Pre-filters (deterministic, from metadata only):** JPEG; width ≥ 480 and height ≥ 320; aspect ratio ≤ 2.5; the title
  must not match `logo|icon|diagram|drawing|illustration|poster|advert|screenshot|map|flag|stamp|label|vector|clipart|render|symbol|pictogram|sign|infographic|painting|cartoon|svg`;
  a file listed under categories of two different classes is dropped.

## Classes and labels
The label of an image is the **class of the Commons category it was drawn from**, checked by a manual rule written
before inference.

| class | source categories (direct files only) | meaning |
|---|---|---|
| `water` | Bottled water; Water bottles; brand and mineral-water categories (Evian, Nongfu Spring, Aquafina, Poland Spring, Volvic, Voss, ...) | a bottle or a pack of plain drinking water |
| `medicine` | First aid kits and its country / museum sub-categories; Military first aid kits; Tabloid First Aid Box; Medical bags | a first-aid kit, box, case or bag |
| `neither` | Toolboxes; Red boxes; Soft drink bottles; Wine bottles; Medicine bottles; Cardboard boxes; Pallets, Wooden pallets, Empty shop shelves; Crates; Shoe boxes; Briefcases; Plastic boxes; Ammunition boxes | confusers: other bottles, other boxes, red boxes without a cross, empty platforms |

Confuser types are recorded per image (`type`) for the secondary analysis.

**Label audit (before inference).** Commons categories are noisy (the "Bottled water" category holds relief-aid photos,
buses, portraits). `scripts/q_contact_sheet.py` renders contact sheets of all 1 079 candidates. Every candidate was
looked at once, **without any model output**, and kept only if it meets the class criterion; otherwise it is on the
exclusion list `experiments/q_exclusions.json` with a reason code. Criteria:
* **water (W):** a sealed bottle or pack of plain drinking water (plastic or glass) is the main subject. Excluded:
  W1 the bottle is small or the scene is dominated by something else (vehicle, building, meal, text); W2 people dominate;
  W3 the contents are not identifiable as plain water (flavoured or coloured drink, empty or antique bottle, unreadable);
  W4 not a bottle (jerry can, 19-litre carboy, metal can or flask, carafe); W0 any other failure.
* **medicine (M):** a first-aid kit, box, case, bag or wall-mounted first-aid box is the main subject. Excluded: scenes
  with people, loose contents or dressings only, signs, posters, drawings, doctors' bags, categories that turned out not to
  hold first-aid kits (the "SNCF - Kit assistance" meal boxes, an AED trainer, packaging); M0 any other failure.
* **neither (N):** a photograph whose main subject is the confuser object, with no drinking-water bottle and no
  first-aid kit as the main subject. Excluded: drawings, text close-ups, people or animals dominating, scenes where the
  object is incidental; N0 any other failure.
The audit was done by the AI assistant that wrote this study (Claude, Sonnet 5.5), not by a human. A reviewer can redo
it with the same sheets. The criterion is class membership only; difficulty for the model is not a reason to exclude.
**The exclusion list is frozen with this registration** (sha256 in `q_sample_final.json`); changing it after the first
inference is not allowed. Audit rounds: round 1 (580 candidates) kept 254 (water 56, medicine 92, neither 106), which was too few for water and
medicine; round 2 added 326 candidates (brand categories, museum categories, more confusers) and round 3 added 173 (more
water), both drawn and audited before any inference. In total 1 079 candidates were audited and 433 kept
(water 139, medicine 121, neither 173). 1 092 files were downloaded; 13 files drawn in round 1 were later dropped by the
class-clash rule.

## Sample and requests
* `scripts/q_eval.py --sample` → `experiments/q_sample_final.json`: from the kept images, at most 8 per (class, photographer)
  (near-duplicate series do not dominate a class), then at most 150 per class, drawn with seed `Q-2026`.
  **Result: 405 images: water 139, medicine 116, neither 150** (neither: toolbox 26, red box 23, soda bottle 22, wine bottle
  21, medicine bottle 16, cardboard box 14, empty shelf / pallet 8, shoe box 7, plastic box 5, briefcase 4, crate 3,
  ammunition box 1).
* **Requested supply**, seed `Q-2026`, balanced: exactly half of the `water` images request water and half medicine; the
  same for `medicine`; half of the `neither` images request water, half medicine.
  * **must-approve** (requested = present): 70 water + 58 medicine = **128**;
  * **must-refuse:** 127 wrong-supply (69 water images asked for medicine, 58 medicine images asked for water) +
    150 neither = **277**.

## Endpoints
**Primary (Qwen3.5-9B check, Wilson 95% CIs):**
* **E1 false approvals:** approved images among the 277 must-refuse images.
* **E2 correct approvals:** approved images among the 128 must-approve images.

**Claim (fixed now).** "The supply check transfers to real photographs" is supported if **both**
* the Wilson 95% **upper bound** of the false-approval rate on all must-refuse images is ≤ 0.05
  (with n = 277, at most 6 false approvals), **and**
* the point estimate of the correct-approval rate is ≥ 0.70.

Otherwise we report which criterion failed: "unsafe" if E1 fails; "safe but conservative" if only E2 fails. The
simulator system and all closed-loop results are unchanged; Q measures one component on one image distribution.

**Secondary (descriptive).**
* False approvals by kind of refusal (wrong supply; each confuser type) and correct approvals by class, with Wilson
  CIs. Types with ≥ 3 false approvals are named. Per-type n is 1–26, so type-level rates are not tested.
* **Baselines (study Z):** SigLIP `google/siglip-so400m-patch14-384` and CLIP `openai/clip-vit-large-patch14`, with Z's
  prompts and Z's frozen thresholds (arg-max is the requested supply and its probability ≥ 0.34; no hazard term, no refit
  on Q). Paired exact McNemar tests against the VLM check on the must-refuse and the must-approve images, and Z's claim
  rule ("safer" / "more available" / "no significant difference", p < 0.05).
* τ_s sensitivity (0.5, 0.7, 0.9), descriptive only; the registered operating point is τ_s = 0.5.

## Threats (stated in advance)
* Commons is not a random sample of the world: photographers choose clean product shots, and `medicine` includes many
  museum objects (tins, wooden boxes) that look unlike a modern first-aid box. A pass here does not prove robustness on a
  robot camera at 0.5 m.
* Wrong-supply refusals (a water bottle when medicine was requested) are easy for a closed-set classifier by
  construction; the confuser types are the informative part, and they are small per type.
* Labels come from category membership plus an AI-performed audit; some residual label noise is possible in both
  directions, and the exclusion rule removes the images that are not clearly of the class, which makes the sample
  easier than the raw category.
* Thumbnails are 960 px; the server resizes to 640 px (as for the robot).
* Qwen3.5-9B may have seen Commons images in pre-training; this cannot be excluded.

## Execution and cost
`q_fetch.py` (done) → `q_contact_sheet.py` and audit (done) → `q_eval.py --sample` (done) → `q_eval.py --run` (Qwen3.5-9B,
two passes per image, 405 images; about 25 GPU minutes on the V100 with model load) → stop the server → `q_eval.py --zeroshot`
(SigLIP and CLIP with Z's four views, about 5 GPU minutes) → `q_analysis.py`. Outputs: `experiments/results/q_scores_*`,
`q_summary.json`. Tests: `tests/test_study_q.py` (sampling determinism, label logic, analysis on synthetic scores).

## Amendments
(none)
