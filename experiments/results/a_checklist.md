# Study A checklist (C0-C9): HEADLINE_HOLDS

Ledger 226 of 226 final rows

| check | status | what |
|---|---|---|
| C0 | PASS | 226/226 runs, 0 failed, registration PASS |
| C1 | PASS_RUNS_OFFLINE_PENDING | advice-audit failures 0, outcome-audit problems 0 kinds |
| C2 | PASS | 43/43 deliveries: baseline approves; violations 0, unverified 0 |
| C3 | PASS | naive/filtered relax |
| C4 | PASS | unsafe per arm, ours-vs-control, eps vs W |
| C5 | PASS | A2 time |
| C6 | PASS | A3 price |
| C7 | INFO | A-steer wording |
| C8 | INFO | extraction |
| C9 | INFO | claim-level failures |

## Verdict

* C3: naive unsafe worlds [12, 12], filtered [12, 12], monotone [0, 12]; A1 p 0.000488 (12:0), A1b p 0.000488
* C4: monotone-unsafe-where-control-safe ['A165', 'A200']; closed-loop vs W: {"W_eps_any_k2": 0.0397, "W_ci95_independent": [0.0136, 0.1109], "monotone_D_unsafe": [2, 16], "monotone_D_wilson95": [0.035, 0.3602], "interval_overlaps_W": true, "above_W": false, "rule": "4 or more of 16 (25%) or a Wilson lower bound above W upper bound: closed-loop eps is above the image-level value (arrival jitter, V lesson); Sec. 1.1 item 2(e) becomes a finding and the \"eps small enough\" sentence is rewritten, not the table"}
* C5: 6/6 positive, median 27.125 s, p 0.0312
* C6: W 33.73 s, bound 50.59 s, max extra 41.74, lost 0 (allowed 4) -> PASS
* C7: steering direction observed but not significant
* C8: operator exact 36/72, intent accepted 72/72
* C9: failed A claims []; Nfailed 7 -> 7

## Unsafe deliveries of the monotone family (C2 replay; images)

* A165 (monotone, AD06): baseline approves True, images ['outputs/runs/3bccb15d4eb84940/checkpoint.jpg', 'outputs/runs/3bccb15d4eb84940/peek_L_checkpoint.jpg', 'outputs/runs/3bccb15d4eb84940/peek_R_checkpoint.jpg']
* A200 (monotone, AD08): baseline approves True, images ['outputs/runs/a11f0d2c60ac488a/checkpoint.jpg', 'outputs/runs/a11f0d2c60ac488a/peek_L_checkpoint.jpg', 'outputs/runs/a11f0d2c60ac488a/peek_R_checkpoint.jpg']

Flags for wording / claim level: none.
