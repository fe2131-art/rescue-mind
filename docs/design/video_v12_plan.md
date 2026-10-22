# Video v12 plan (not built; v11 is 2:51 and does not mention GL or QI)

Status: v11 (`outputs/video/PAI最終課題_tetsutetsu.mp4`) was made before study GL. **Do not upload v11 until this plan is decided.** Limit: 1-3 min (budget 175 s, 3 s spare in v11), speed-up stated on screen.

Changes (storyboard of `docs/video_plan.json`, built by `scripts/make_video_plan.py`):
1. **Table card (part 9, 20 s):** the depot sentence "倉庫は5件のまま" is out of date. New wording from `gl_summary.json`: depot, fresh 120 worlds, v3.6 20 -> left-only 0.8 m look-around with a calibrated threshold 6 (paired p = 0.00066; site-specific; default unchanged). Numbers must be computed from the result file, as for the other lines.
2. **QI card (new, 6 s, after the depot mission, part 8):** one image strip from the real run: simulator frame -> photo-realised frame (QI-R) -> generator-drawn fire in the clean twin (QI-G, e.g. `outputs/qi/G_pilot/G_xd233_R.jpg`) -> gate verdict. Narration: states that the images are generated, not real photographs, and gives the QI numbers once `qi_summary.json` exists (claims held or failed, as they come out).
3. **Time:** +6 s is over the budget, so drop part 5 (card "記憶が慎重さを足した例（評価H）", 5 s; its content stays in the paper) and shorten the closing card from 5 s to 4 s.
4. The speed-up text on screen stays as in v11.

Build only after the QI campaign ends (rendering is CPU heavy): `make_video_plan.py` with the old run ids, then `render_after_film.sh`, then check length <= 175 s, `check_consistency.py`, README/YouTube description (`make_youtube_description.py`).
