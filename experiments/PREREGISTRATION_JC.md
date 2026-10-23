# Pre-registration — study JC: JEV with a divided role (a fast sentinel decides where to look; the gate decides), analysis of study JI's scores

Status: REGISTERED 2026-10-23 (this commit, before any JI image is rendered or scored). Design note: `docs/design/jev_roles_plan.md`; `docs/IMPROVEMENT_LOG.md` I-100. No GPU: it re-reads the JI scores.

## Why
Study JH used the second judge as a redundant veto (same question, same views, `max`): by base world it removed one fire (I-93). A second opinion on the same image does not add what a better observation adds (six views: 14 → 5 misses at 0 false stops, post hoc). Six views cost drive time (about 8.4 s per extra view in GL: 43.8 s with two 0.4 m peeks against 35.4 s with one 0.8 m peek). The judge's possible advantage is speed, so give it the job that only needs speed: **decide whether the three extra views are worth driving.** The sentinel can neither approve nor refuse; a sentinel false alarm costs views (time), never a delivery, and the refusal is the gate's own (Prop. 2 unchanged, false-stop budget the gate's).
**Measured before this registration (disclosed):** the selected judge is *not* faster: median scoring time of InternVL3-8B is 6.2 s per image (four passes) against 2.15 s for a gate view (`jev_scores_internvl3_xd.jsonl`, `devset_xd_h36_tiles.json`); Qwen3-VL is 0.8 s but is the gate's family; SmolVLM2 and Idefics3 have no latency recorded in XD. JI's scoring will record all four. So "fast" is checked, not assumed.
**Post hoc development on XD (`scripts/cascade_dev.py`, `cascade_dev.json`; one image set, seen before registering):** gate on F, L, R misses 14; always six 5 (6 views); the gate's own low-score trigger at 0.01: 7 misses, 3.78 views on clean worlds; InternVL3 sentinel (alpha_s = 20%): 6 misses, 3.43 views, 0 false stops; SmolVLM2: 8 misses, 3.49 views; Idefics3: 8, 3.63. It is the hypothesis, not a result.

## What is run
Policy (`scripts/ji_cascade.py`): the sentinel scores F, L, R; if its per-world maximum reaches its frozen threshold the robot spends the extra views L2, R2, N and the gate decides on all six (tau6 = 0.088), otherwise on F, L, R (tau3 = 0.088). Thresholds: gate from `experiments/ji_thresholds.json`; sentinel from `experiments/ji_cascade_thresholds.json` (rank rule at alpha_s = 20% on XD's clean calibration worlds, frozen before JI exists). Nothing is fitted on JI. **Primary sentinel = the judge with the lowest median scoring latency in JI among InternVL3, Idefics3, SmolVLM2** (a rule). Compared with always-three, always-six and the gate's own trigger (score on F, L, R ≥ 0.01, the existing adaptive-views idea of I-20). All four judges and the alpha curve are reported.
Time model (descriptive): extra views × (8.4 s drive + the gate's median per-view time) + 3 × the sentinel's median latency; stated, not measured in a closed loop.

## Claims (explicit)
* **JC1:** the primary sentinel's misses ≤ always-six misses + 3 (on 120 fresh fire worlds).
* **JC2:** mean views per clean world ≤ 4.0 (3 = no extra view, 6 = always six).
* **JC3:** the primary sentinel's false stops ≤ 5 of 120 (the limit of JI3).
* **Descriptive predictions (failing them is reported, not a failed claim):** P1 the primary sentinel misses fewer fires than always-three; P2 its estimated extra time per clean mission is below always-six's.
* A failed JC claim goes to the failed-claim list. JC is only meaningful if JI's own claims JI1 (six views) hold; if JI1 and JI2 fail, JC is reported as moot and the sentinel idea is dropped from the paper's claims.

## Known limits, stated now
Image level: no closed loop, no drive-time measurement (8.4 s is borrowed from GL); the sentinel threshold comes from one simulator image set; a sentinel that runs on a moving robot (frames while driving) is not tested; the fast judge may turn out not to be fast (then P2 fails and the paper says so); GPU memory next to the gate in a closed loop is only enough for SmolVLM2 (about 4.5 GB beside 19 GB), not for InternVL3 (about 16 GB).
