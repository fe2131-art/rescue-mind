# Provenance of the git history (one-time rewrite, 2026-10-26)

日本語の要約：2026-10-26 に `main` の履歴を一度だけ書き換え、コミットメッセージ末尾の Claude の `Co-Authored-By` 行（806 行・805 コミット）だけを除いた。
ソース・結果・PDF・タイムスタンプ証明・作者・日時・親子関係・マージは変えていない。元の履歴は公開タグ `archive/pre-claude-attribution-rewrite-20261026` に残してあり、
登録台帳・論文の表・OpenTimestamps の対象テキストが引用するコミットハッシュは、元の履歴のものである。

## What changed and what did not

| | before (original history) | after (`main`, rewritten) |
|---|---|---|
| head | `286756a717389aea3b9f88465bc73d0e2c653c82` | `76f69aad66c1148f534c08013a31827eb709c834` (later commits are added on top of it) |
| commits / merges | 911 / 47 | 911 / 47 |
| root tree of the head | `025d04a46b6a1cd6d8508d34a330f1992832d569` | the same |
| commits with a Claude `Co-Authored-By` trailer | 805 (806 lines) | 0 |
| author and committer (name, email, time, zone) of every commit | | identical |
| tree and parent order of every commit | | identical |
| `v3.3.0` (annotated tag object `a8e2c5fdafba8dec529b428e1115bb4e4e19c199`, commit `5c9a951f9bab3d0fee48172ee7f158b602a97f02`) | | **not changed**; it still points to the original commit |
| `archive/pre-claude-attribution-rewrite-20261026` (annotated tag) | | new; points to the original head `286756a…`; keeps every original commit and message public |

Only lines that are Claude co-author trailers were removed from commit messages (`Co-Authored-By: Claude … <noreply@anthropic.com>`); every other byte of every commit is the same,
except that each parent hash is replaced by the hash of the rewritten parent.
The 911 original commits and the 911 rewritten commits are paired one-to-one; the pairing is published in `docs/provenance/commit_map_20261026.tsv` (original, rewritten).

## Verify it yourself

```bash
git fetch origin tag archive/pre-claude-attribution-rewrite-20261026     # a normal clone already has it
python3 scripts/verify_history_rewrite.py --check-map docs/provenance/commit_map_20261026.tsv
```

The script walks the original and the rewritten history in parallel (parent *i* with parent *i*) and checks, for every pair, the tree, the author and committer headers, the number
of parents, and that the message differs only by removed Claude trailer lines. It does not recompute any hash, so it is independent of how the rewrite was done.

## What the timestamps prove (and do not)

* `docs/timestamps/*.txt.ots` are OpenTimestamps proofs of the **bytes** of the `*.txt` files next to them. The texts quote commit hashes **of the original history**.
  Both the texts and the proofs are unchanged by the rewrite.
* The proofs do **not** attest the hashes of the rewritten `main`; they cannot, because those hashes did not exist when the proofs were made.
  The original commits are still addressable by their original hashes through the archive tag.
* On 2026-10-26 all 26 proofs were checked: each proof's digest equals the SHA-256 of its text, and 71 Bitcoin attestations were replayed to the Merkle root of the attested block
  (block roots read from blockstream.info; no Bitcoin node was used, so the explorer is a trust assumption). Result: 26 of 26 verified, 0 problems.
  Run it again with `pip install opentimestamps && python3 scripts/verify_timestamps.py`; for a node-independent check use `ots verify` with your own node.

## Registration order, ledger and paper tables

The ledger `docs/REGISTRATIONS.md` and the paper tables (`docs/paper/tab_prereg.tex`, `tab_amend.tex`, `numbers.tex`) are generated from git history
(`scripts/make_registrations.py`, `scripts/paper_numbers.py`). Their hashes are those of the **original** history, because the hashes are quoted by the time-stamped texts.
The generators therefore read the archive tag when it exists (otherwise HEAD, so a clone that still has the original history behaves as before):

* `python3 scripts/make_registrations.py --check` and `make numbers` reproduce the committed ledger and tables byte for byte on the rewritten `main` (with the archive tag present).
* `git merge-base --is-ancestor <registration> <first results>` is an ancestry test: use **original** hashes with the **original** history (the archive tag), or the rewritten hashes
  (from the commit map) with `main`. An original hash is not an ancestor of the rewritten `main` (no original commit is part of it), so mixing the two fails by construction.
  Example for study G: `H=refs/tags/archive/pre-claude-attribution-rewrite-20261026; git merge-base --is-ancestor edb26a1 f6160fb && echo "registration predates results"`
  (both short hashes are original ones and are resolved through the archive tag's objects).

## Notes

* The old commit pages on GitHub keep showing the Claude trailer: the original history is public on purpose, as the evidence behind the time stamps.
  The Contributors graph of `main` counts only the rewritten history, and GitHub may take up to about a day to refresh it.
* A backup bundle of the original history was made before the rewrite (SHA-256 `0290ced54004b54188c869928b6aae2c37ee3d22c2812e4c6f37515527cc33f9`) and restored into a separate clone to compare
  the head, the tags and the tree. It is not part of this repository; the archive tag contains the same history.
