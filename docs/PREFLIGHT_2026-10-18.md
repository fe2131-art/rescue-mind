# Pre-flight of the queued GPU studies (2026-10-18)

Static check of every script in the queue A (rerun) -> IF -> S -> B -> XD -> X -> Q, on the state "main + i21-depot merged"
(fast-forward merge verified in a scratch clone), without starting a stack, a server or Gazebo. Dry runs of the generators, the
orchestrator in `--plan` mode (all 226+27 A, 48+6 B, 80+9 X trials), the SDF builders (XD 628, S 234, A/B/X 390 worlds) and the
analysis steps on synthetic input all ran in a scratch clone. Fixes are commits with the prefix `preflight:`.

## Verdict

| study | verdict | what stood in the way / what was done |
|---|---|---|
| A (rerun) | READY after Amendment 1 | the old pilot ledger must be moved aside (`run_campaign.py` skips finished trials whatever their stack arguments); `a_run.sh` now refuses a stale ledger, runs its registration gate before the pilot, and checks the container and port 8765. `make_protocol_a.py` got `INTENT_PROMPT` / `--intent-prompt TAG --amend` (default output unchanged = registered) |
| IF | READY | registered files committed, `Status: REGISTERED`, analysis runs on synthetic input. Added: a parser-error guard (the registered rule counts an error as a refusal, so a dead server would look like a perfect defence) |
| S | READY (was BLOCKED) | `s_eval.sh` ran the VLM server on the host python, which has no `transformers` (the wait loop `until curl ... ready` would have hung forever). Now: server in rm-next via `docker exec -d` (like IF/Q), bounded wait, OCR masking on the host (the OCR venv is invisible in the container), result files and analysis exit code checked. `s_render.sh` retries 3x (resumable) |
| B | READY | gate, generator = registered, `--plan` of all trials OK. Added: container / port / stale-ledger guards |
| XD (a) | READY (was BLOCKED, same cause as S) | `xd_eval.sh` fixed as `s_eval.sh`; `xd_render.sh` retries 3x; all 628 world SDFs build, depot assets present, `xd_smoke_ok` present |
| XD (r) | NEEDS THE USER | `~/.cache/rescuemind/warehouse_negatives/` (>= 200 fire-free, licensed photographs plus `manifest.jsonl`) does not exist. Stage r is not in the default stages; if requested without the data it is now skipped with `XD_NOTE`, stage a is unaffected |
| X | READY | pilot/main protocols = generator, the steer-selection path (select -> `--force` -> commit) runs on synthetic masks, `--plan` OK for 89 trials, depot assets complete. Added: registration gate (there was none), container / port / stale-ledger guards |
| Q | READY (was BLOCKED) | the zero-shot step ran in rm-next, whose venv lacks `sentencepiece` (SigLIP tokenizer: ImportError). Now `Q_ZS_CONTAINER` (default rm-dev, which has it and the GPU). 405 images present with matching sha256, final sample regenerates identically. Added: pass-error guard (> 5%) |

## Findings and checks

* Host `python3` (3.10, torch 2.4.1) has no `transformers`, `huggingface_hub`, `accelerate`; rm-next has transformers 5.20 but no `sentencepiece`
  / `pandas` / `z3`; rm-dev has `sentencepiece`. Host-side scripts (analyses, clients, `q_eval.py --run` in `pqvenv`) import only numpy/scipy/PIL/stdlib: OK.
* Registered protocol = generator output for A, A pilot, B, B pilot, S, X, X pilot, XD; `make_intent_flip_set.py`, `make_advice_injection_set.py`
  and the Q final sample reproduce their files; `advice_prompts_frozen.json` matches the prompts.
* Registration gates (`ls-files` + `git diff HEAD`) pass on the merged tree. The merge main + i21-depot is a fast-forward with no
  untracked-file conflicts (main's untracked files vs i21's tracked ones: none).
* Weights: Qwen3.5-9B snapshot = `PINNED_REVISIONS` (c2022362...); SigLIP and CLIP snapshots present. OCR venv works offline (3 synthetic images masked).
* S: sign check image is upright and unmirrored (no transform needed); `sign_check_ok` present. XD: `xd_smoke_ok` tracked and present.
* Pkill / pgrep: all `pkill -f local_vlm_server*` run inside rm-next or as a script file (no self-match); the pgrep guards cover
  `gz sim|run_campaign|v32_orchestrate|local_vlm_server`. No script kills anything else.
* Git steps (a_run, b_run, x_run commit + push with explicit pathspecs after `git add`): no hooks; a failed push only prints a note.
* Disk 1 TB free (about 300 MB per run with rosbag).
* Incident of this pre-flight: the first dry runs of `make_protocol_{a,b,s,x,xd}.py` (called with `--help`, which they ignore) were run in the main checkout and rewrote
  the protocol and advice files with identical content (`git status` stays clean, only mtimes changed). Everything after that ran in a scratch clone.

## Amendment 1 of study A, steps

1. `python3 scripts/make_protocol_a.py --intent-prompt i38 --amend` and the same with `--pilot`; also set `INTENT_PROMPT = 'i38'` in the script so the generator test keeps matching the file.
2. Append the Amendment to `PREREGISTRATION_A.md`, `mv experiments/results/campaign_A_pilot_ledger.jsonl experiments/results/campaign_A_pilot1_ledger.jsonl`, commit, push.
3. `bash scripts/a_run.sh` (the guard refuses to start if step 2 was forgotten).

## Chain notes

`bash scripts/s_eval.sh` and `bash scripts/xd_eval.sh` are run on the host (as in the old chains); `s_render.sh` / `xd_render.sh` in rm-next.
`S_STAGES=m` masks the OCR images on the host only. Sandbox dry run of `s_eval.sh` / `xd_eval.sh` with stub docker/curl: server start/stop per stage, bounded wait
abort, stage r skipped without data.
