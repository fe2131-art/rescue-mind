# Registration ledger (generated 2026-10-18 09:25 from `git log` on main)

A pre-registration binds from the first commit in which it is on `main`; the "first-parent" history of `main` gives that
commit. The pre-registrations of A, B, IF, Q, S, X and XD reached `main` with the integration merge `587f033` at
2026-10-18 09:08 JST:
* study A's pilot started at 09:14;
* IF, S, B, XD, X and Q had not run any trial or inference at that time.

Some of these files still carry a "DRAFT" line in their own text. That line describes the draft stage *before* the merge.
The binding version is the one in the table below. The text of a registration is not edited after the merge, so that it
stays byte-identical up to the amendments. An amendment is only appended, with its own date and commit (table "Amendments" below).

Verify any row:
`git log --first-parent --format='%h %cI' --diff-filter=A -- experiments/PREREGISTRATION_X.md` (first commit on main),
`git merge-base --is-ancestor <registration commit> <first result commit>`, and `sha256sum experiments/PREREGISTRATION_*.md`.
An external timestamp of these hashes (OpenTimestamps) is not done yet; it needs the owner's consent.

| file | on main since (commit, time) | last change on main | sha256 (first 16) |
|---|---|---|---|
| PREREGISTRATION_A.md | 587f033 2026-10-18T09:08 | 2a1bab0 2026-10-18T10:09: (Amendment 1, appended) | 0f1fbb16fee2cc9e (1532940eadc11b24 when bound) |
| PREREGISTRATION_B.md | 587f033 2026-10-18T09:08 | 1c04256 2026-10-18T03:10: | 7416ff27901695cf |
| PREREGISTRATION_E.md | 6201aa0 2026-10-16T21:13 | 6201aa0 2026-10-16T21:13: | b720abb71a27d057 |
| PREREGISTRATION_F.md | 564a724 2026-10-17T04:11 | 1ed0992 2026-10-17T17:08: | d4624001f32c6f3a |
| PREREGISTRATION_G.md | edb26a1 2026-10-17T06:14 | 1ed0992 2026-10-17T17:08: | e133dfd0b3207e47 |
| PREREGISTRATION_H.md | a5cc651 2026-10-17T10:07 | 1ed0992 2026-10-17T17:08: | 1746630b8c4f71dc |
| PREREGISTRATION_IF.md | 587f033 2026-10-18T09:08 | 051e530 2026-10-17T23:59: | 38e510bfab955f30 |
| PREREGISTRATION_J.md | b72b877 2026-10-17T10:53 | 8163f88 2026-10-17T17:17: | 887819e218fc866a |
| PREREGISTRATION_K.md | 3a21238 2026-10-17T16:06 | 3a21238 2026-10-17T16:06: | 2f31f46703d0d092 |
| PREREGISTRATION_L.md | a3b0540 2026-10-17T20:09 | f0f3d52 2026-10-17T19:06: | 844369c89e2ff087 |
| PREREGISTRATION_P.md | e6bde02 2026-10-17T11:32 | e6bde02 2026-10-17T11:32: | b4b6d195df0be8bf |
| PREREGISTRATION_P2.md | 72f0309 2026-10-17T11:54 | 2910b2e 2026-10-17T12:09: | 5bb954f894fba52c |
| PREREGISTRATION_Q.md | 587f033 2026-10-18T09:08 | c7d06b3 2026-10-17T20:58: | 7af0a5ac72d46fd4 |
| PREREGISTRATION_R.md | fb63bee 2026-10-17T09:45 | fb63bee 2026-10-17T09:45: | 5e0551b7bc87ada9 |
| PREREGISTRATION_S.md | 587f033 2026-10-18T09:08 | 5535660 2026-10-17T22:43: | d322457d6cafff4a |
| PREREGISTRATION_T1.md | 5f835af 2026-10-16T19:50 | 4ad4f4f 2026-10-16T20:49: | 7f9307be8c29190b |
| PREREGISTRATION_T2.md | f347239 2026-10-17T00:02 | 418f1c8 2026-10-17T04:20: | 8c1f78aff6fefd2c |
| PREREGISTRATION_V.md | b23210f 2026-10-17T17:50 | abf0c98 2026-10-17T18:10: | 5176b22d985f37df |
| PREREGISTRATION_W.md | b2a6dbe 2026-10-17T18:57 | cc0e103 2026-10-17T22:42: | aa34a1dafb4378b1 |
| PREREGISTRATION_X.md | 587f033 2026-10-18T09:08 | 2e8972d 2026-10-17T23:13: | d283f926675fcb86 |
| PREREGISTRATION_XD.md | 587f033 2026-10-18T09:08 | 5535660 2026-10-17T22:43: | 5cd006c872c61619 |
| PREREGISTRATION_Z.md | a53ee7e 2026-10-17T11:28 | 0ca401d 2026-10-17T11:44: | 09b8480b5a3d34d8 |
| PREREGISTRATION_v33.md | 5c9a951 2026-10-16T12:42 | 5c9a951 2026-10-16T12:42: | 7b7e09ef639af4e7 |
| PREREGISTRATION_v34.md | ac6d815 2026-10-16T16:18 | fb4e9b3 2026-10-16T16:21: | 1d7513a8dc750006 |

## Amendments

Generated for the paper as the amendments table of the Registration Audit, Supplement S9 (`docs/paper/tab_amend.tex`, from `scripts/paper_numbers.py`: one row per amendment heading, the
commit that introduced it, and the first results commit of the study). Amendments after the binding of 2026-10-18 09:08:

| study | amendment | commit (git time) | what changed | any registered trial before it? |
|---|---|---|---|---|
| A | 1 | 2a1bab0 2026-10-18T10:09 (the text says 10:30; the commit time is authoritative) | intent prompt i38 instead of i35 for every A run (`common_stack_args`), after the mechanics pilot of 09:14 (27 runs, i35) failed on the operator channel (FINDINGS #30); adopted by the rule fixed before it was evaluated (I-25: `experiments/results/intent_i38_check.json`, held-out 55/60 for both prompts, 0 unsafe; dev injection correct acceptances 86 to 92 of 94, 0 wrong shelter; test half untouched). Protocols regenerated, only `common_stack_args` changed. First pilot ledger kept: `experiments/results/campaign_A_pilot1_ledger.jsonl`. | no: `a_summary.json` and the campaign ledger do not exist; the pilots are mechanics runs, not registered trials |
| B | 1, 2 | ed8e48b 2026-10-18T01:38; 1c04256 2026-10-18T03:10 | before the binding merge, before the pilot and any B trial | no |

The default of the v3.6 robot stays i35; study IF measures i35, as registered. The sha256 of `PREREGISTRATION_A.md` in the table above is the amended text;
the text as bound at 09:08 had the sha256 prefix `1532940eadc11b24`.
