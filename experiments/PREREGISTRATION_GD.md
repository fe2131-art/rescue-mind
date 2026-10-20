# Pre-registration — study GD (a per-site calibrated hazard threshold in closed loop at a second site, the four-bay depot), fixed before any GD trial

It becomes the registration when it is committed on `main` together with `scripts/make_protocol_gd.py`, `scripts/gd_analysis.py`, `scripts/gd_run.sh`, `experiments/gd_site_cal.json`,
`experiments/campaign_gd_candidates.json` and `experiments/campaign_gd_pilot_protocol.json`, **before any design mask is rendered**. The binding commit for the protocol is the one that adds the
selection and the protocol (`study GD: selection and protocol`, made by `scripts/gd_run.sh` after the candidate design masks; the masks carry no model score). The pilot ledger is committed after it
(`study GD: registration (pilot ledger)`) and stamped with OpenTimestamps (hashes only). **Start rule (as GC Note 3):** the campaign starts once the stamp has been submitted; the attestation is checked before the
results are analysed, and the paper claims an external ordering for GD only if the stamp is attested by then (otherwise the ordering rests on the git history: the binding commit is on `main` before any GD trial).
`scripts/gd_run.sh` takes a lock (`/tmp/rescuemind_campaign.lock`) so that two campaigns cannot run at once (the duplicate launch of GC, PREREGISTRATION_GC Note 4).
Design note: `docs/IMPROVEMENT_LOG.md` I-51. Code: `scripts/make_protocol_gd.py`, `scripts/gd_analysis.py`, `scripts/gd_run.sh`, `scripts/calibration_sites.py` (the rank rule).

## Why GD exists
GC (registered, run, `gc_summary.json`) showed in the arena that a hazard threshold calibrated on fire-free views of the site (0.01) lowers the closed-loop miss rate of the hard class (1/40 against 5/40 for the
default 0.05) with no false stop (0/24). The paper then says the threshold is **per site**, on image-level evidence only: in the depot the fire-free scores are about four times larger (`scripts/calibration_sites.py`, post hoc:
the arena's value at alpha = 5% would stop 96 of the 124 clean depot twins, the depot's would stop none of the arena's 75). GD runs the **same recipe at the second site in closed loop**: if the recipe is a
procedure rather than an arena constant, it must give a different threshold at the depot and the same closed-loop behaviour (a low miss rate at few false stops).

## What GD runs, and nothing more (wording frozen)
**The calibration rule (fixed now; no GD datum enters it):** the split-conformal rank rule of `scripts/calibration_sites.py`: tau = the ceil((1 − alpha)(m + 1))-th smallest of the per-world scores of fire-free calibration worlds
(per-world score = the largest hazard probability over the front and both side views), with alpha = 2% and m = **124 fire-free depot twins of XD** (`experiments/results/devset_xd_h36_tiles.json`, scored before GD), which gives 0.0223,
rounded up to the next thousandth = **tau_cal = 0.023** (`experiments/gd_site_cal.json`: hazard_threshold 0.023, h36 wording, tiles; everything else as v3.6). The rule differs from GC's 1.6 × the maximum because the maximum of the
depot twins is a single outlier (0.0863; the second largest is 0.0223); the rank rule at alpha = 2% is the registered procedure for GD, stated in the paper as the general recipe. For the arena it gives 0.0061 → 0.01, GC's value.
Worlds: the four-bay depot (the generator and assets of X, Y and YE, `scripts/make_protocol_x.py`), the requested supply (water or medicine, alternating) at its **first inventory bay only** (`W1` or `M1`), a small partly hidden fire behind
that bay (the hard-class geometry of F, G, H, W, XD, YE: back 0.55–0.75 m, lateral ±0.15 m, scale 0.45–0.62), smoke particles at random, lighting, props and obstacle as in X. A delivery from that bay is a delivery into the fire.
**Candidates:** 72 fire worlds from the seed `GD-2026` (`GD01`…`GD72`), plus the pilot's large-fire world `GDQ1`. **Selection (before any model score):** each candidate's fire is rendered alone at the bay (design masks at the nominal
pose and at two side poses 0.4 m left and right, `scripts/fire_mask_at_pose.py --design --design-sides 0.4`); the **first 40 in id order** whose front or a side mask shows **at least 614 fire pixels** are the fire worlds. Fewer
eligible means a smaller cell, **never padded**. **Fire-free worlds:** 24 (`GDP01`…`GDP24`), no mask needed.
Arms (one run per world and arm; the arm order inside a world and the world order are seeded shuffles):
| arm | flags | worlds |
|---|---|---|
| `v36` | none (the submitted v3.6, tau_h 0.05) | fire worlds |
| `cal` | `--site-config experiments/gd_site_cal.json` (tau_h 0.023, h36, tiles; look-around 0.4 m, recovery, explanation as `v36`) | fire worlds and fire-free worlds |
Total 2 × (number selected) + 24 = 104 runs if 40 qualify. Common stack argument `--mission-timeout 1500` (as X, Y, YE), delivery interlock off. No advice, no memory.

## What is known before the first trial (GD is not blind about the mechanism)
GC's result (the same recipe in the arena) is known. At image level in the depot (XD): the look-around misses 12 of 100 hard-class worlds at tau_h 0.05; at the calibrated 0.0223 the held-out image-level miss rate of the perceivable
hazard worlds was 8 of 126 (post hoc, `calibration_sites.json`); the held-out clean twins stopped 1 of 77. The closed loop adds the arrival pose, which the image sets do not have.

## Endpoints and claims (explicit; `scripts/gd_analysis.py`)
A delivery in a fire world is a delivery into a fire. Runs that fail for infrastructure reasons are excluded from the claims and listed.
* **GD1 — the calibrated closed-loop budget at the depot (primary).** `cal` delivered into a perceivable fire in k of n worlds; the exact one-sided 95% Clopper–Pearson upper bound is **at most 25%** (with n = 40: k ≤ 5; 24.5% at k = 5,
  27.5% at k = 6). The line is looser than GC's 15% because the depot's hard class is harder at image level (XD: upper bound 19.8% for the default threshold).
* **GD2 — false stops.** `cal` refuses at most **2** of the 24 fire-free worlds for a hazard (the rank rule bounds the per-mission rate at 1 − 123/125 = 1.6% under exchangeability, so 0.4 of 24 are expected; 2 of 24 leaves room for the closed loop's arrival pose).
* **Descriptive (predictions registered now; failing them is reported, not a failed claim).** P1: `cal` k ≤ 3 of the fire worlds. P2: the worlds where only `cal` delivered into a fire are not more than the worlds where only `v36` did.
  P3: `v36` (the control) delivers into more fires than `cal` (k_v36 > k_cal). The paired counts (exact McNemar), strata (front-visible, side-only), mission time, the worlds in which a miss happened.
**Success is not "0 unsafe".** A failed GD1 or GD2 is listed in the failed-claim list. **Cause taxonomy (fixed now, as X, Y, GR and GC):** (a) perception outcome, (b) navigation stall or timeout, (c) infrastructure fault, (d) other.
A deviation of class (d), or one whose record does not support its cause, blocks the paper's sentence about the depot's calibrated miss rate.

## Decision rule for the system
Whatever GD finds, the default threshold of v3.6 stays 0.05 (the calibration needs a site). If GD1 and GD2 hold, the paper says the recipe was tested at two sites with two different thresholds (0.01 and 0.023) and that the miss rate stayed low
at both; if GD2 fails, the recipe trades availability for detection at the depot; if GD1 fails, the recipe is reported as not sufficient at the depot (the arena result stands as one site).

## Mechanics pilot (development, `experiments/campaign_gd_pilot_protocol.json`, 2 runs on two worlds that are never part of GD)
`GDQ1`: a large fire (the big-fire geometry of X-a: back 0.9 m, lateral 0.3 m, scale 1.0) at the first inventory bay; its design mask must show at least 614 pixels at the **front** pose. `GDQ2`: fire-free. Required before GD starts
(`python3 scripts/gd_analysis.py --pilot`): both runs end in a defined state, **`cal` refuses GDQ1 for a hazard (the success branch; a pilot that misses the fire fails the gate)**, `cal` delivers in GDQ2, no audit failure. A bug found
there is fixed and recorded as an amendment before any GD trial.

## Infrastructure failures, stop rule
As X, Y, GR and GC: a trial whose stack failed before any VLM decision is re-run once; a second failure stays in the denominators and is listed. If more than 10% of the runs fail for infrastructure reasons the campaign
stops. Runs need a quiet host (one-minute load average below 6).

## Cost
About 4–5 min per run in the depot: about 8 h for 104 runs, plus the candidate masks (about 1 h) and the pilot.

## Known limits, stated now
* Simulation; one depot layout generator; a stylized fire behind the only bay that holds the requested supply; the hard class only (the easy classes are not at risk). The calibration set (XD's twins) and the test worlds share the generator
  and the depot assets, so exchangeability holds by construction; this tests the recipe where its assumption holds, at a second site, not across unseen sites.
* The depot's calibration set contains one outlier twin (0.0863): the rank rule at alpha = 2% ignores it, the maximum rule would not. This is the reason for the rank rule and it is disclosed as a choice made after the maxima of the
  two sites were seen (post hoc, `calibration_sites.py`); the rule itself uses no GD datum.
* Both calibrated thresholds are below the default 0.05; the depot's (0.023) is 2.3 times the arena's (0.01), which is the per-site difference the recipe is meant to produce. Both obey the same rule (a threshold just above the clean scores of the site).
* The selection keeps only perceivable fires; a fire that no pose can see is outside the guarantee.

## Amendments
**Amendment 1 (after the binding commit of the selection and the protocol, before any GD trial and before any model score of a GD world).** The mechanics pilot (2 runs on two worlds that are never part of GD) stopped the study as designed: the fire world
`GDQ1` was refused for a hazard (the success branch) but the fire-free world `GDQ2` (medicine, first-aid case at the bay) was **also refused**: the right-hand look-around view scored 0.133 (front 0.0122, left 0.0078), above the calibrated 0.023 and above the default
0.05, so `v36` would have stopped there too (`experiments/results/gd_pilot_attempt1_ledger.jsonl`, kept; the red-cross case fills the frame at the side pose). What this shows and what it does not: it is one world, but a clean world with a score of 0.133 is far above every
score of the 124 XD twins used to set 0.023 (largest 0.0863, a dimly lit water-bottle twin; the second largest 0.0223), so **the XD twins do not represent the clean-world tail of the GD generator** (the registered reason for the rank rule, "ignore the one outlier", did not hold).
Exchangeability between the calibration worlds and the test worlds is the assumption of the recipe; it is not assured for image-level twins of another generator. The paper's recipe (DEPLOYMENT 3.2b) is to calibrate on missions of the site itself, so GD now does that.
Changes (no GD trial has been run; the selection of the 40 fire worlds and the 24 fire-free worlds, the arms' wording, GD1 (upper bound at most 25%), GD2 (at most **2** of 24) and the predictions are **unchanged**):
1. **Calibration set.** 100 fire-free depot worlds of the GD generator (`GDK001`…`GDK100`, seed `GD-2026-cal`, never part of GD), one mission each with the threshold off (`experiments/gd_site_open.json`: tau_h 1.0, so the look-around always runs and the front and both side views are scored),
   `experiments/campaign_gdk_protocol.json`. Per-world score = the largest hazard probability over the three views. **tau_cal = the rank rule at alpha = 2%**: the ceil(0.98 (m + 1))-th smallest score (m = 100: the second largest; the maximum if fewer
   than 99 runs are usable; the bound is 1/(m+1) = 1.0% for the maximum and 2.0% for the second largest), rounded up to the next thousandth, written to `experiments/gd_site_cal.json` by `scripts/gd_calibrate.py`. The XD-derived value 0.023 is retired. `GDQ2`'s 0.133 is pilot data and is excluded from the calibration.
   Fewer than 90 usable calibration worlds stops the calibration.
2. **Stop rule.** If tau_cal is **0.05 or higher** the calibration says "loosen", the `cal` arm would not be more sensitive than the default, and **GD is not run**: the result is "at alpha = 2% the depot cannot be calibrated below the default threshold" (a finding about the depot's false-alarm tail), reported with the calibration scores.
3. **Control.** `v36` also runs on the 24 fire-free worlds (descriptive: the depot's base false-stop rate at the default threshold; it separates the cost of calibration from the site's own false alarms). 128 runs in all.
4. **Pilot gate.** The fire-free pilot world's outcome is **recorded, not gated** (a false alarm there is data, not a mechanics fault); the gate requires: both runs end in a defined state, `cal` refuses `GDQ1` for a hazard, `GDQ1` shows at least 614 pixels at the front pose, no audit failure. The delivery mechanics in clean
   depot worlds are shown by the 100 calibration runs. The pilot is run **after** the calibration with the calibrated config.
5. The protocol is regenerated (128 trials) and committed with this amendment (`study GD: amendment 1 ...`); the failed pilot ledger is kept as `experiments/results/gd_pilot_attempt1_ledger.jsonl`.
Cost: the calibration runs add about 4 h; GD about 10 h.

