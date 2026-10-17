#!/usr/bin/env bash
# Stop study R (resumable: finished conditions are kept). Run from a file: pkill -f inside bash -c kills its own shell.
pkill -f 'scripts/r_eval.sh'; pkill -f r_corruption_eval; pkill -f local_vlm_server; true
