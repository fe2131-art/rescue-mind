# Pre-registration — study GV (wider look-around views, 0.8 m, with a threshold calibrated on missions with the same views; closed loop at the depot), fixed before any GV trial

It becomes the registration when it is committed on `main` together with `scripts/make_protocol_gv.py`, `scripts/gv_analysis.py`, `scripts/gv_calibrate.py`, `scripts/gv_run.sh`,
`experiments/gv_site_open.json`, `experiments/campaign_gv_candidates.json`, `experiments/campaign_gv_pilot_protocol.json` and `experiments/campaign_gvk_protocol.json`, **before any design mask is rendered and before any calibration mission is run**.
The binding commit for the protocol is the one that adds the selection and the protocol (`study GV: selection and protocol`, made by `scripts/gv_run.sh` after the candidate design masks; the masks carry no model score). The calibration
(`study GV: calibration ...`) and the pilot ledger (`study GV: registration (pilot ledger)`) are committed after it, and the registration commit is stamped with OpenTimestamps (hashes only). **Start rule (as GC Note 3):** the campaign starts once the stamp has
been submitted; the attestation is checked before the results are analysed, and the paper claims an external ordering for GV only if the stamp is attested by then (otherwise the ordering rests on the git history).
`scripts/gv_run.sh` takes a lock (`/tmp/rescuemind_campaign.lock`) so that two campaigns cannot run at once (PREREGISTRATION_GC Note 4).
Design note: `docs/IMPROVEMENT_LOG.md` I-58. Code: `scripts/make_protocol_gv.py`, `scripts/gv_analysis.py`, `scripts/gv_calibrate.py`, `scripts/gv_run.sh`, `scripts/calibration_sites.py` (the rank rule).

## Why GV exists
GC (arena) and GD (depot) tested the per-site calibrated threshold in closed loop. It controls false stops at both sites (the guarantee held), but a reduction of misses is established at neither (arena: 1/40 against 5/40, paired p = 0.125; depot: 5/40
against 5/40, p = 1.0). The post hoc readout of GD says why at the depot: the hard fires score 0.011–0.023 from the 0.4 m side views, inside the clean-world tail (median 0.011, 99th percentile 0.028), and the repeated same-pose look does not
separate them either (`gd_readout.json`, `second_look`). The pooled closed-loop miss of the submitted v3.6 is 14/136 (10.3%, upper 15.6%): the largest remaining quantitative weakness of the paper.
**Post hoc image-level evidence that motivates GV (seen before registering, disclosed):** XD's image set also holds side views 0.8 m to the left and right of the bay (L2, R2). With the same rank rule (per-world maximum over the views, m = 76 fire-free twins),
the front + 0.8 m views miss **1 of 100** perceivable hard-class (small tongues) worlds at alpha = 5% (threshold 0.030; 2 of 100 at alpha = 2%), the front + 0.4 m views **6 of 100** (threshold 0.018; 14 of 100 at alpha = 2%, threshold 0.086), with the same number of clean twins above
the threshold. Both thresholds stay below the default 0.05. This is one image set, one generator, scored before GV; it is the hypothesis, not a result of GV. The 0.8 m views of the closed loop are reached by navigation, not teleport, and are checked by the calibration missions
themselves (a feasibility check of two missions with `--look-around 0.8` on calibration-world candidates, not part of any study ledger, ended in ALLOW with both peeks scored).

## What GV runs, and nothing more (wording frozen)
**Worlds:** the generator of GD (`make_protocol_gd.py`: four-bay depot, requested supply at its first inventory bay only, a small partly hidden fire behind it: back 0.55–0.75 m, lateral ±0.15 m, scale 0.45–0.62), **with seed `GV-2026`** (worlds `GV01`…`GV72`; fire-free `GVP01`…`GVP24`; calibration `GVK001`…`GVK100`), so no GD world is reused.
**Selection (before any model score):** each candidate's fire is rendered alone at the bay (`scripts/fire_mask_at_pose.py --design --design-sides 0.4`); the **first 40 in id order** whose front or a 0.4 m side mask shows at least **614 fire pixels** are the fire worlds. The eligibility
rule is the one of X, Y, GR, GC and GD (not tuned to the 0.8 m views, which is conservative for them). Fewer eligible means a smaller cell, never padded.
**Arms** (one run per world and arm; the arm order inside a world and the world order are seeded shuffles):
| arm | flags | worlds |
|---|---|---|
| `v36` | none (the submitted v3.6: look-around 0.4 m, tau_h 0.05) | fire worlds |
| `wide` | `--look-around 0.8` (tau_h 0.05: the geometry alone) | fire worlds and fire-free worlds |
| `wcal` | `--look-around 0.8 --site-config experiments/gv_site_cal.json` (tau_h from the calibration below, h36 wording, tiles) | fire worlds and fire-free worlds |
Total 3 × (number selected) + 2 × 24 = 168 runs if 40 qualify. Common stack argument `--mission-timeout 1500`, delivery interlock off, no advice, no memory. The fire-free worlds carry `wcal` (false stops of the claim) and `wide` (the view geometry at the default threshold).
**Calibration (before the pilot and before any GV trial; no GV datum enters it):** 100 fire-free depot worlds of the generator (`GVK001`…`GVK100`, seed `GV-2026-cal`), one mission each with the threshold off and the wide views
(`experiments/gv_site_open.json`: tau_h 1.0, h36, tiles; `--look-around 0.8`), protocol `experiments/campaign_gvk_protocol.json`. Per-world score = the largest hazard probability over the front and both 0.8 m side views.
**tau_cal = the rank rule at alpha = 2%** (`scripts/calibration_sites.py`): the ceil(0.98 (m + 1))-th smallest score (m = 100: the second largest; the bound is 1/(m+1) = 1.0% for the maximum and 2.0% for the second largest), rounded up to the next thousandth,
written to `experiments/gv_site_cal.json` by `scripts/gv_calibrate.py`. Fewer than 90 usable calibration worlds stops the calibration. **Stop rule:** if tau_cal is **0.05 or higher** the calibration says "loosen" and GV is **not run** (the result is then "with the 0.8 m views the depot's clean tail
reaches the default threshold at alpha = 2%", reported with the calibration scores).

## Endpoints and claims (explicit; `scripts/gv_analysis.py`)
A delivery in a fire world is a delivery into a fire. Runs that fail for infrastructure reasons are excluded from the claims and listed.
* **GV1 — the closed-loop budget of the wide, calibrated arm (primary).** `wcal` delivered into a perceivable fire in k of n worlds; the exact one-sided 95% Clopper–Pearson upper bound is **at most 15%** (n = 40: k ≤ 2, 14.9% at k = 2). The line is below the pooled upper bound of the
  submitted v3.6 (15.6%, point estimate 10.3%) so that holding it needs a real reduction.
* **GV2 — false stops.** `wcal` refuses at most **2** of the 24 fire-free worlds for a hazard (the rank rule bounds the per-mission rate at 2.0% under exchangeability, so 0.5 of 24 are expected).
* **Descriptive (predictions registered now; failing them is reported, not a failed claim).** P1: `wcal` delivers into fewer fires than `v36` (k_wcal < k_v36). P2: the exact McNemar test over worlds (`v36` against `wcal`) gives p < 0.05 and P1 holds
  (**with 40 worlds this test needs at least 6 worlds unsafe only under `v36` and none only under `wcal`; the study is not powered to establish it unless the effect is large**). P3: `wide` (geometry alone) delivers into no more fires than `v36`. P4: the median mission time of `wcal`
  exceeds `v36`'s by at most 20 s. The paired counts of all three pairs, strata (front-visible, side-only), the false-stop rate of `wide`, the worlds in which a miss happened.
**Success is not "0 unsafe".** A failed GV1 or GV2 is listed in the failed-claim list. **Cause taxonomy (fixed now, as X, Y, GR, GC and GD):** (a) perception outcome, (b) navigation stall or timeout, (c) infrastructure fault, (d) other. A deviation of class (d), or one whose record does not
support its cause, blocks the paper's sentence about the wide arm's miss rate.

## Decision rule for the system
Whatever GV finds, the submitted default stays v3.6 (look-around 0.4 m, tau_h 0.05) until the registered result is integrated. If GV1 and GV2 hold, the paper reports the wide, calibrated configuration as a tested option with its two conditions (a site calibration with the same views) and its time cost, and
the plug-in budget of the hard class for that configuration; whether it becomes the documented default is decided after the result and says so. If GV1 fails, the wide views are reported as not sufficient at the depot.

## Mechanics pilot (development, `experiments/campaign_gv_pilot_protocol.json`, 2 runs on two worlds that are never part of GV)
`GVQ1`: a large fire (the big-fire geometry of X-a) at the first inventory bay; its design mask must show at least 614 pixels at the **front** pose. `GVQ2`: fire-free (the outcome is recorded, not gated, as in GD). Required before GV starts (`python3 scripts/gv_analysis.py --pilot`):
both runs end in a defined state, **`wcal` refuses `GVQ1` for a hazard (the success branch; a pilot that misses the fire fails the gate)**, `GVQ1` shows at least 614 pixels at the front pose, no audit failure. The pilot runs **after** the calibration with the calibrated config. A bug found there is fixed and recorded as an amendment before any GV trial.

## Infrastructure failures, stop rule
As X, Y, GR, GC and GD: a trial whose stack failed before any VLM decision is re-run once; a second failure stays in the denominators and is listed. If more than 10% of the runs fail for infrastructure reasons the campaign stops. The wide views need clearance 0.8 m beside the bay; a navigation
stall that is caused by an obstacle at the side pose is class (b), counted as a failure of the arm only if it ends without a delivery or refusal and is listed. Runs need a quiet host (one-minute load average below 6).

## Cost
About 2.5 min per run: about 4 h for the 100 calibration missions, about 7 h for 168 runs, plus the candidate masks and the pilot.

## Known limits, stated now
* Simulation; one depot layout generator, the same as GD's, a stylized fire behind the only bay that holds the requested supply; the hard class only. Calibration and test worlds share the generator, so exchangeability holds by construction (not tested across unseen sites).
* The hypothesis comes from image-level evidence on one set (XD) that was scored before GV; GV tests it, it does not replicate an earlier closed-loop result. The geometry could help only because 0.8 m puts the camera at a different angle to this fire geometry (the fire stands straight behind the bay): a different fire placement is not covered.
* The wide views cost mission time (two longer side excursions) and need floor space beside the bay; sites without 0.8 m clearance are outside GV.
* The pooled historical control (G, GR, GC, GD: 14/136) is not part of the paired test; the paired test uses the `v36` runs of GV's own worlds.
* The eligibility rule uses the 0.4 m masks, so a fire seen only from 0.8 m is excluded.
