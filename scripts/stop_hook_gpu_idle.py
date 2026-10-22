#!/usr/bin/env python3
"""Claude Code Stop hook (I-72): the assistant may not end its turn while the GPU / campaign queue is idle.

Stop hook protocol: JSON on stdin ({"stop_hook_active": bool, ...}); printing {"decision": "block", "reason": "..."} makes the conversation continue with `reason` as the next instruction.
Idle = `scripts/idle_check.sh` exits 1 (no campaign, GPU job or orchestrator process).  The hook blocks while idle and tells the assistant to launch the first open job of docs/GPU_QUEUE.md now.
A second rule (I-79): jobs running but no `bg_watch.sh` process (no visible background task) also blocks, so the user never sees an empty background list.
Loop guard: at most MAX_BLOCKS consecutive blocks without a job appearing (a real blocker, e.g. a dead container, must not burn tokens forever); the counter resets when a job runs.
A tracker file records every decision (outputs/stop_hook_gpu_idle.log) so the user can audit it.  Any hook error allows the stop (never wedge the session).
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = Path('/tmp/rescuemind_stop_hook_idle.json')
LOG = ROOT / 'outputs/stop_hook_gpu_idle.log'
MAX_BLOCKS = 6

REASON = ("STOP REFUSED: the GPU / campaign queue is IDLE (scripts/idle_check.sh exit 1). Small document fixes do not count as work. "
          "Do this now, in this turn: (1) read docs/GPU_QUEUE.md and take the first open job; if its result says nothing is justified, add the next job to the queue (a development pass, a replication or a pooled-budget run) - an empty queue is not an answer; "
          "(2) commit its protocol, then start it with Bash run_in_background (check `pgrep -fa 'run_campaign|gvd_run|gv_run|gd_run'` and the load first; key a waiter on the job PID); "
          "(3) re-run `bash scripts/idle_check.sh` and only then continue or end the turn. Blocks so far without a running job: {n}/{max}.")


REASON_WATCH = ("STOP REFUSED: jobs are running but no visible background task watches them (the user sees 'no background task'). "
                "Start `bash scripts/bg_watch.sh` with Bash run_in_background now (it ends, and notifies, when the queue ends), then continue or end the turn. Blocks so far: {n}/{max}.")


def watched() -> bool:
    return subprocess.run(['pgrep', '-f', r'^bash scripts/bg_watch\.sh$'], capture_output=True, timeout=30).returncode == 0


def idle() -> bool:
    r = subprocess.run(['bash', str(ROOT / 'scripts/idle_check.sh')], capture_output=True, text=True, timeout=60)
    return r.returncode == 1


def log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {msg}\n')
    except OSError:
        pass


def decide(is_idle: bool, state: dict, max_blocks: int = MAX_BLOCKS, is_watched: bool = True) -> tuple:
    """-> (output dict or None, new state).  Pure, for the test.  Idle -> launch a job; running but unwatched -> start the visible watcher."""
    if not is_idle and is_watched:
        return None, {'blocks': 0}
    n = int(state.get('blocks', 0))
    if n >= max_blocks:
        return None, {'blocks': n}                      # loop guard: allow the stop, keep the count until a job runs
    reason = REASON if is_idle else REASON_WATCH
    return {'decision': 'block', 'reason': reason.format(n=n + 1, max=max_blocks)}, {'blocks': n + 1}


def main() -> int:
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    try:
        state = json.loads(STATE.read_text()) if STATE.is_file() else {}
        i = idle()
        out, new = decide(i, state, is_watched=True if i else watched())
        STATE.write_text(json.dumps(new))
        log(f'{"BLOCK" if out else "allow"} state={new}')
        if out:
            print(json.dumps(out, ensure_ascii=False))
    except Exception as e:                              # never wedge the session
        log(f'hook error, allowing: {e!r}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
