# HANDOFF — RescueMind

作業を中断・文脈圧縮した後でも、**この最初の画面だけで**正確に再開できるようにまとめたもの。
構成：**現在地（今ここ）→ 履歴（要約）→ 参照（§2 実行環境・§3 コマンド・§4 落とし穴・§7 ファイルの地図）**。
旧版の全文（日付ごとに積み重なっていた節）は `docs/HANDOFF_ARCHIVE.md` に**一字も変えずに**残してある。細部（PID、当時の連鎖、日付ごとの判断の理由）が必要なときだけ見ればよい。
数値は結果ファイル（`experiments/results/*_summary.json`）と台帳から読み直したもの。文書の数値は `python3 scripts/check_consistency.py` が結果ファイルと突き合わせる（HANDOFF の数値は手で書いたので、結果が変わったらここも直す）。

---

## ★ 最新（2026-10-23 17:00）：GM 実行中（192/264）、JI → IG → JC が待機、JEV を「速さを活かす見張り役」へ（I-93〜I-100）

* **GPU の順番（すべてバックグラウンド、`flock /tmp/rescuemind_campaign.lock`）**：`gm_run.sh`（192/264 試行、失敗は再実行で解消、終了は 22〜23 時ごろ）→ `ji_run.sh`（描画3時間＋ゲート1.3時間＋審判4×1時間）→ `ig_run.sh`（依頼文の解析、約3分。ロックを取るので JI と順不同でも衝突しない）。`bg_watch.sh` を常に1つ動かす。
* **登録済み（拘束コミット＋OTS）で結果待ち**：**JI**（6視点の再現、JI1〜JI4）、**IG**（凍結した依頼解析を新しい依頼文136件で検証、IG1・IG2、`experiments/intent_eval/ig_v1.jsonl`）、**JC**（JEV を「追加視点を取りに行くかを決める見張り役」にする。JI のスコアを GPU なしで読み直す `scripts/ji_cascade.py`、JI_DONE の後に実行）。登録済みファイルと `ji_run.sh` は **JI が終わるまで編集禁止**。
* **JEV の立場（ユーザーに説明済み）**：評価JH の「見逃し29〜43%減」は元の世界で数えると11→10（1世界）。選んだ InternVL3 は速くない（1画像6.2秒、Qwen の1視点は2.15秒）。速さを活かすには小型の審判（SmolVLM2）。計画は `docs/design/jev_roles_plan.md`。閉ループ版は GPU メモリ（Qwen 約19 GB の隣に載るのは SmolVLM2 だけ）と閉ループ較正が要るので、JC/JI の結果を見てから登録。
* **各結果が出たら**：失敗した主張フック・論文マクロ（`JI*` `IG*` `GM*`）・README 行は準備済み（合成の要約で動作確認）。残るのは補足資料の節（`ji_section.tex`、`ig`、`jc`）、FINDINGS #51〜、IMPROVEMENT_LOG の Result、動画の証拠カード。
* **GM 終了後に必ずやること**：論文の全ビルド（`bash scripts/rebuild_docs.sh`、文献2本と README 変更の反映）、説明資料の再生成（テスト件数表記）、動画 v13 の再生成（冒頭の一文、I-98）、`bash scripts/final_check.sh`（全実行）。
* **この日の改善**：I-96 文献2本（Hidden Clones、SmokeBench）、I-97 README の最初の画面（30秒で、動画リンクを上へ、結果表を6行＋折りたたみ）、I-98 動画の冒頭、I-99 IG、I-100 JC。

## ★ 最新（2026-10-23 12:00）：GM 本実行中（264試行、約13時間、2026-10-23 11:40 開始）

* **GM（I-92、`experiments/PREREGISTRATION_GM.md`）**：GL の左のみ見回しが、現実感の要素を1つ外した倉庫（照明・散らかり・周囲・台）でも効くか。`bash scripts/gm_run.sh`（バックグラウンド、再開可能）。台帳 `experiments/results/campaign_GM_ledger.jsonl`、完了で `GM_DONE`、解析は `scripts/gm_analysis.py` → `gm_summary.json`。**実行中は CPU の重い処理（全テスト・ビルド・描画）禁止**（静かなホスト）。
* **GM が終わったら**：`gm_summary.json` を読む → `cp docs/paper/gm_section.draft.tex docs/paper/gm_section.tex` と Reading を結果に合わせて書く（マクロは `GM*` 済み、失敗した主張フックと README 行は準備済み）→ FINDINGS #50、TRIAL_AND_ERROR、IMPROVEMENT_LOG I-92、HANDOFF 件数 → `bash scripts/final_check.sh`（全項目）→ 動画の証拠カード（GL の行の横に GM を足すか判断、枠は9行・20秒）。
* **完了済み（本日）**：QI 結果反映（QI3 のみ成立、失敗した主張18件）、QJ 結果反映（QJ1〜3 すべて成立、0/120 ×3）、動画 v12（2:51）、サーバーのセキュリティ対応（pip・uv・Node・CA・Docker イメージ、`docs/SECURITY_RESPONSE_2026-10.md`。残りは管理者の root 作業）。
* **未実行の最終確認**：`final_check.sh` のユニットテスト（GM の実行中は不可）。

## ★ 最新（2026-10-23 昼）：QI 結果反映（I-88〜I-91）、動画 v12 完成、QJ・GM を準備

* **ユーザー指示（/goal 更新）**：実写は見送り。強い結果を出す改善、**最終確認を常に**（`bash scripts/final_check.sh`、QUICK=1 で軽量版）、動画更新、レポートに頁数制約なし、アドバイザーに相談。
* **QI の結果（反映済み）**：QI3 のみ成立（誤停止 0/104）。QI1 不成立（写実化で見逃し 14→26/126）、QI2 は登録した停止規則（炎の色のない画像 140/205）で停止、QI3c 不成立（対照編集 39/72、生成器が煙を描いた）。失敗した主張は18件。FINDINGS #48（48件）、補足節 `qi_section.tex`。G2・K1・K2（記述のみ）は採点中、終われば補足節に一文足す。
* **動画 v12（2:51、171.0秒）**：証拠カードに GL・JH・QI、QI の対比画像カード（`docs/figures/qi_strip.png`、`make_qi_strip.py`）。旧版は `_v11_backup.mp4`。**アップロードはユーザー**。
* **I-91**：右視点の閾値案は既存データで効果なし（負の開発結果、研究は登録しない）。
* **次の GPU（順番）**：QI2 完了 → QJ（テキスト生成の新シーン。`experiments/PREREGISTRATION_QJ.md` は下書き、パイロットで FLAME_MIN を決めて Amendment 1 → コミット → OTS → `bash scripts/qj_run.sh`。アドバイザー指摘：N0 もパイロットに入れ、FLAME_MIN は清浄画像が通らないように決める） → GM（GL が現実感の変種でも成り立つか。`experiments/PREREGISTRATION_GM.md`、`bash scripts/gm_run.sh`、約13時間、静かなホスト）。
* **最終確認の初回結果**：7項目不合格のうち、ページ判定・登録一覧・カード幅・YouTube 概要欄は修正済み。QI2 完了後に `final_check.sh` を再実行して0にする。

## ★ 最新（2026-10-23 朝）：GL 成立、JH1 不成立、QI 生成中（I-83〜I-86）

* **GL 完了（I-84）**：GL1・GL2・GL3 すべて成立。倉庫の新しい120世界で、火への配達 v3.6 20/120 → 左のみ0.8 m 6/120（p=0.00066、誤停止 2/40）。効くのは正面から見えない火（側方のみ 16/24 → 3/24）。サイト固有の選択肢で、既定は v3.6 のまま。論文は補足（GL の節）・限界の節・要旨に反映済み。倉庫の基線（pooled）には GL の v3.6 腕も含めた（I-86）。
* **JH（I-80）**：JH1 不成立（15件目の失敗した主張）。補足に JH の節。
* **実行中（バックグラウンド）**：`bash scripts/qi_run.sh`（研究 QI：R 768枚→G 205→C、`--fast` で1枚14秒）→ 続けて `bash scripts/qi_run2.sh`（訂正2：G2 大きな火、K1 ベスト、K2 警告灯、約615枚）。監視は `bash scripts/bg_watch.sh`。結果は `experiments/results/qi_summary.json`。事前登録は `experiments/PREREGISTRATION_QI.md`（訂正1：マスクの色判定と写実化プロンプト、訂正2：記述的な拡張、訂正3：世界得点は欠けた視点を双子の元スコアで補う／写実化の火が残ったかの監査 `scripts/qi_r_audit.py`）。
* **QI が終わったら**：(1) `python3 scripts/qi_r_audit.py`、見逃した写実化世界を目で確認（火が消えたか・残って見逃したか）、(2) `qi_summary.json` を読む（基線は 14/126 と 0/104 に一致するはず。失敗した主張は `advice_numbers.failed_claims()` が自動で拾う）、(3) 補足に QI の節（マクロは `paper_numbers.py` に準備済み、引用は ROSIE・Cosmos-Transfer1・Sim2Real Diffusion・SPIE・合成煙の領域差）、(4) FINDINGS・TRIAL_AND_ERROR・README、(5) 全テスト、`/tmp/rebuild.sh` 相当の再ビルド、本文8頁・要旨200語、(6) **動画 v12**（`docs/design/video_v12_plan.md`。v11 は GL を含まないのでそのまま YouTube に上げない）、(7) FINAL=1 ビルドと SUBMISSION_CHECKLIST。
* **失敗の教訓**：同一ファイルへの書き込みは1本だけ。`pkill -f` のパターンを自分のコマンド行に含めない（シェルが死ぬ）。画像を見る前に採点へ進まない（QI のマスクと写実化の欠陥は目視で見つかった）。

## ★ 最新（2026-10-21 13:50）：研究 GV は登録した停止規則で中止（I-58、I-60）。本番168試行は実施していない

* **結果**：火のない倉庫100世界（閾値を切った実ミッション、失敗0）の較正で、2%の規則の閾値 **0.071**（0.05 以上）→停止規則が働き、GV は走らせない。0.4 m の視点（GD）は 0.028。既定 0.05 のままでも100世界中4世界が止まる。主張 GV1・GV2 は未検証（失敗した主張には**数えない**）。登録の拘束コミットは `350d14a`（結果 `76f7920` より前）。外部 OTS は作っていない（予行の後の手順のため）。
* **事後の読み**（`scripts/gv_stop_readout.py`、I-60）：0.03 以上の7視点はすべて薬の箱の右 0.8 m 視点（赤い十字が画面を占める。最高4枚を目視）。水は最大 0.027。XD の画像にはこの偏りがない（薬の最大 0.0385）。GD の見逃し配達10件中9件（較正腕5件すべて）が薬の世界。**仮説であり未検証**。
* **反映済み**：補足資料 `sec:moved-gv`、main.tex の一文、README 行、レポート表、YouTube 説明文、FINDINGS #44（44件）、`paper_numbers` の `WideStop*` マクロ。`gv_summary.json` が無いので Wide 系の本番用フックは動かない（停止時用のフックは動く）。
* **赤い十字の案は却下**（I-61、FINDINGS #45）：質問文に1文足すと火のない世界の閾値は下がるが火の得点も下がる（検出 71→68・63/80、見逃し10件のうち届くのは1件）。見逃しは較正でも質問文でもなく、その姿勢での小さな火の得点の低さ（I-62）。閉ループの試験は登録しない。
* **次**：視点の取り方（幾何）を変える案は、画像レベルの根拠が閉ループに移らなかった経緯（XD→GV）から、先に既存の閉ループ画像で見積もれる範囲を確認してから。それ以外は最終確認（全テスト・check_consistency・SUBMISSION_CHECKLIST）。
* 以前の「GV を実行中」の記述は廃止（上のとおり中止）。
* **★ 毎回の最初に `bash scripts/idle_check.sh`**（I-71）：IDLE なら同じターンで `docs/GPU_QUEUE.md` の先頭を起動する。GPU を空けたまま文書修正だけをしない。現在 **GVD（0.8 m 視点の開発パス、I-70）が実行中**、結果は `python3 scripts/gvd_readout.py`。次の IMPROVEMENT_LOG は **I-72** から。
* **仕上げ磨き（2026-10-21 夜、I-64〜I-68、すべて push 済み）**：I-64 監督テストの不安定さの原因は負荷ではなく、バックグラウンド起動で SIGINT が無視のまま子に継承されること（テストを修正）。I-65 新規 clone で全テスト 1564 通過・16 スキップ（倉庫アセット未取得分 10 を含む）・不一致 0（`REPRODUCTION_RECORD.md`）。I-66 要旨の分母の重複を削除（196 語）。I-67 表の見出しから「pending」を削除。I-68 main.pdf の「Supp. Sec. ??」を修正し、`check_consistency` に両 PDF の「??」検査を追加。次の IMPROVEMENT_LOG は上の行のとおり。


## ★ 最新（2026-10-21 08:00）：研究 GD 完了・反映済み（I-51、I-53、I-54、I-55）

* **GD の結果（128本、失敗0、OTS 承認済み）**：較正は倉庫の火のない100本（閾値オフ、実ミッション）で τ_cal=0.028。**GD1 成立（5/40、上限24.5%、登録線25%の縁）、GD2 成立（誤停止 1/24）**。だが**見逃しは減らなかった**：既定 0.05 も 5/40、対の差 2 対 2（McNemar p=1.0）、予測 P1（≤3）と P3 は外れ、P2 は成立。較正腕の見逃し5件の得点は 0.0107〜0.0233（τ_cal 未満）で、火のない世界の裾（中央値 0.011、99%点 0.028）に入る。同じ世界・視点でも走行ごとに最大約13倍変わる（GD37 左 0.023 対 0.301）。新しい火のない24世界は較正の最大 0.0415 を超えず、誤停止は保証どおり。
* **読み**：較正の手順は誤停止の保証（サイトをまたいで成り立つ）であり、見逃しの削減は**どちらのサイトでも有意でない**（arena 4対0 p=0.125、倉庫 2対2 p=1.0。GC の 5/40→1/40 も「確立」とは言えない）。v3.6 の閉ループ見逃し（G・GR・GC・GD 対照）は **14/136（10.3%、上限15.6%）**：論文・DEPLOYMENT・README の予算の数字はこれに更新済み。失敗した主張は14のまま（登録主張は不成立なし）。FINDINGS #43。
* **反映済み**：補足資料の GD 節（`sec:moved-gd`）、main.tex（GR–GD の一文。本文8頁・9頁目は参考文献のみ）、README、説明資料（本文9頁）、概要欄、DEPLOYMENT（3.2b と表）、FINDINGS #43、図 `fig_calibration`（GD の曲線入り）。`gd_readout.py` は実行済み。
* **動画**：v10 の証拠カードに GD の行は未追加（20秒枠。必要なら `scripts/make_video_plan.py` を直して再描画。レシピは上の GC の項）。

## ★ 最新（2026-10-20 23:00）：研究 GC 完了・反映済み（I-45、I-47、I-48、I-49）

* **GC の結果（104本、失敗0、OTS 承認済み）**：GC1 成立（較正腕 1/40、上限11.3%、登録線15%）、GC2 成立（誤停止 0/24）、予測 P1・P2 とも成立。対照の v3.6 は 5/40（すべて横からしか見えない火）で、G・GR・GC を合わせた v3.6 の閉ループ見逃しは 9/96（9.4%、上限15.8%）。較正腕との差 4対0 は McNemar p=0.125 で有意でない。失敗した主張は14のまま。
* **反映済み**：補足資料 GC の節（Reading と split-conformal 上限）、main.tex の予算の段落、README、説明資料（本文9頁）、DEPLOYMENT（3.2b の較正手順と 9/96）、FINDINGS #42、概要欄。動画：証拠カードに GC を足し `outputs/video/v10_candidate.mp4` を作成中（できたら ffprobe で確認し、`PAI最終課題_tetsutetsu.mp4` に差し替える。旧版は `_v9_backup.mp4` に退避）。
* **GC の二重起動事故**：Note 4 参照。`gc_attempt3_overlap_ledger.jsonl` は解析から除外して保存。
* **次の候補**：論文本文8頁を保つ。新しい研究の候補は、較正集合の大きさ（m）と誤停止の関係の閉ループ検証、depot での較正、実写での較正。

## ★ 最新（2026-10-20 19:30）：研究 GC を実行中（I-45、I-46）

* **GC（サイトで較正した閾値 0.01 の閉ループ、新しい40世界×2腕＋火のない24世界＝104本）**：`GC_NO_OTS_WAIT=1 bash scripts/gc_run.sh`（ログ `experiments/results/gc_run.log`、台帳 `campaign_GC_ledger.jsonl`、約7〜8時間）。登録は Amendment 1・Note 2・Note 3。完了後：`python3 scripts/gc_analysis.py`（run が自動実行）→ `ots upgrade docs/timestamps/study_gc_registration.txt.ots`（確定を解析の前に確認）→ 補足の GC 節（草稿は scratchpad の gc_supp_draft.tex、マクロは paper_numbers の GC ブロック）、main.tex に1文、README/説明資料/概要欄（フックは用意済み）、動画の評価カード行、FINDINGS #42、I-45 の Before/After、`failed_claims`（GC1・GC2 が崩れたら自動で入る）。
* **GC の再起動（19:45、PREREGISTRATION_GC Note 4）**：自分で GC を二重起動し、2 本の run_campaign が同じ台帳に書いて 48 行中 18 行が基盤失敗になった。両方を止め、その台帳は `gc_attempt3_overlap_ledger.jsonl` として残して解析から除外し、空の台帳から単独実行で再開（104 本、約 7〜8 時間）。**GC を再度起動しない**（`pgrep -fa run_campaign` で確認）。部分集計を一度見たことも Note 4 に開示済み。
* **I-46（FINDINGS #41）**：`--site-config` がオーケストレーターの実行経路でミッションに渡っていなかった。修正と回帰テスト済み。
* **方針（ユーザー指示 10/20）**：自分で足した進め方の規則（確定待ち、重い処理の禁止など）で改善を遅らせない。ユーザーの規則（公開設定を変えない、rm禁止、個人情報なし、履歴は指示があるまで触らない）は守る。

---

## ★ 最新（2026-10-20 18:00）：研究 GR（見回しの閉ループ再現）完了

* **GR（新しい40世界・92本・失敗0、拘束コミット 8b9c519、OTS 確定）**：GR1・GR2・GR3 は成立（v3.6 の火への配達 3/40・上限18.3%、見回しなし 21/40、McNemar p=1e-5、誤停止 0/12）。**予測 P3 は不成立**（横からしか見えない火 2/6）。閉ループの見逃し 7.5% は画像評価Wの2%より高く、Gと合わせた 4/56（7.1%、上限15.6%）が予算。失敗した主張は14件のまま。FINDINGS #40、I-44。
* **反映済み**：論文（本文8頁、要旨198語、補足 J 節、Table S9）、説明資料（6頁の箇条書き、本文9頁）、README、DEPLOYMENT.md、動画の評価カード行（`make video` で v9_candidate.mp4 を描画中。最終名に置く前に確認）。
* **CI が赤だった原因と修正**：YE・hazard-continue のテストが z3 とデポ資産を要求していた（スキップ指定にした）。`build_paper.sh` の FINAL 検査は結果マクロだけを数える。
* **運用**：cron `b12aac41`（毎時 23 分）は「確認だけの巡回」を禁止し、登録済みGPU研究の前進か I-xx の改善コミットを必須にしている。長い処理は `run_in_background`、キャンペーン中は重い CPU 処理をしない。

---

## ★ 最新（2026-10-20 12:30）：凍結確認

* **最終動画 169.6 秒（2:50）を設置済み**。全テスト 1493 件成功（6 件スキップ）。`check_consistency` 0 不一致、`secret_scan` 0 件、`public_release_audit` PASS（未追跡の `.claude/` を対象外にした）。
* **CI が赤だった原因**：新しい YE・Y のテストが z3 とデポ資産を要求していた。CI には無いのでスキップ指定にした（d919988）。結果は次の実行で確認する。
* **説明資料**：6 頁の評価 V・A・Y の段落を箇条書きにした（本文は 9 頁のまま）。提出チェックリストは main 一本の手順に書き換え、概要欄の上限は文字数（5000 文字、現在 約 3700）。
* **次**：`make paper FINAL=1` の通し、CI の緑確認、論文の査読目線の磨き込み。新しい研究は始めない（残り日数に対し密度が増えるため）。ユーザー作業は従来どおり（履歴の個人パス除去は指示があるまで触らない、public 化、YouTube、omnicampus、選出フォーム）。

---

## ★ 最新（2026-10-20 01:30）：YE・YF 完了、失敗した主張は14件

* **YE（2つの火、24本）**：v36 は 0/12、フラグ付きは 2/12 で隠れた第2の火へ配達（上限 43.8%）。**YE2 は登録文言の誤りで不成立**（13件目、直さず残した。事後の読みは `scripts/ye_readout.py`）。予行ゲートは失敗の枝で通っていた（FINDINGS 38）。
* **YF（新しい世界、27本）**：Y1・Y3 成立、tighten-only の見逃しは再現（FC27）。**YF4 不成立**（14件目、本物の失敗）：火のない双子で scrutiny が4拠点を訪れ配達できず。**P3 不成立**（scrutiny＋フラグの失う配達 YF 1/9、Y 0/15、合わせて 1/24）。改定1（候補バッチ2を追加、拘束コミット d2050be）の経緯は `experiments/PREREGISTRATION_YF.md` 末尾。
* **反映済み**：論文（本文8頁、要旨200語）、補足の YE・YF 節、説明資料の評価Y段落と反省の項、README（英語ブロックは `update_readme_results.py` が生成）、導入ガイド 4.7、YouTube 概要欄、動画計画（冒頭カードで新しい点を先に言う。証拠カードは「続行+scrutiny 喪失 1/24」）。
* **次**：動画の再描画（v8、`outputs/video/v8_candidate.mp4`）を最終名に置く → `make_youtube_description.py`・`update_submission_facts.py` → 第三者採点 第11回 → 最終凍結（FINAL=1）→ ユーザーへ引き継ぎ。個人パスの履歴除去は、ユーザーの指示があるまでしない。
* **運用の教訓**：長い処理は `run_in_background` で、定期の確認や通知への一言返信はしない（ユーザー指示 10/19）。待ち時間は文書・ビルド（`nice`、1〜3コア）に使ってよい。待機ループの `pgrep -f` は、自分のコマンド行に一致して詰まることがある。

---

## ★ 最新（2026-10-19 18:30）：I-42 と研究 Y が完了

* **作業場所は main に一本化した**（i21 は main の祖先。論文・補足・README・report はすべて main で更新済み、`check_consistency` 0 不一致、本文 8 頁）。i21 の worktree の未コミット変更（sec_formal・FINDINGS）は main に取り込み済みで、触らなくてよい。
* **I-42**：`--hazard-continue`（既定オフ）。本物の危険を見た棚だけ拒否し、探索を続ける。命題 2 は不変、z3 は 154 件で期待どおり（134 unsat＋20 sat）、変異 16 個とも検出。
* **研究 Y（51 本、失敗 0）**：拘束コミット 9c0b5e8、登録コミット 678ab40、OpenTimestamps は Bitcoin で確定（38c7052）、結果 7dd3bc3。**Y1–Y4 成立**（P2 は安全側だけ成立、双子での拒否は 6 本中 4 本。逸脱 7 本は原因 (a)、`scripts/y_readout.py` で裏づけ）。scrutiny＋フラグは対照比で配達を失わない（0/15）。tighten-only は XC05 で火へ 3/3 配達（知覚の見逃し、P1 どおり）。**測っていない**：追加訪問の露出コスト（清潔な棚に火がない）。A1 は証明の範囲外。失敗した主張は増えない（12 のまま）。
* **次にやること**：(1) 第三者採点 第 11 回（`docs/evaluations/EVALUATOR_PROMPT.md`、Y 統合後）。(2) `ots upgrade docs/timestamps/registrations_manifest_20261019.txt.ots`（Bitcoin 確定後）。(3) 最終凍結（FINAL=1 ビルド、`docs/SUBMISSION_CHECKLIST.md`、動画の証拠カードに Y を足すか判断）。(4) git 履歴の個人パス除去は、ユーザーが「最後に」と言うまで何もしない。
* **ユーザーの追加指示（10/19）**：作業を止めない。「次にやる」と書いたら同じターンで実行する。モニターの通知を待つ間も、軽い作業（文書・下書き・分析）を進める。

---

## ★ 圧縮後はここから（2026-10-19 09:40 更新。方針は 10/18 19:10 のまま）

**ユーザーの方針（最新）**
* **サブエージェントは今後使わない**（10/18 19:10）。すべて自分で行う。
* `rm` は使わない。消すものは `~/rescue-mind-trash/<日時>/` に移し、削除はユーザーに任せる。
* 公開設定は変えない。YouTube 投稿と公開はユーザーが行う。日本語で簡潔に。事前登録し、失敗も載せる。コミットは I-xx で、push まで行う。
* 締切は 2026-11-02 10:00 JST。

**ブランチ**
* main：登録と結果。i21-depot（worktree `.claude/worktrees/i21`）：文書と論文の作業場所。
* 統合マージまでは、HANDOFF は i21 だけで編集する。
* i21 が追跡するファイルを、main の作業ツリーに未追跡のまま置かない（マージが失敗する）。
* `scripts/build_paper.sh` は main の図を再生成するので使わない。worktree では latexmk を直接呼ぶ。

**結果（すべて論文・説明資料・README に反映済み）**
* **A は主張成立**：
  * 悪意ある助言で危険な配達があった世界：素朴 12/12、LLM ガードレール 12/12、本方式 0/12（p=0.0005）。
  * 配達 43/43 は、助言なしの確認でも許可されるものだった。
  * 正しい助言で中央値 27 秒短縮。誘導による配達できなかった世界は 14/16（FINDINGS #33）。
* **IF は不成立**：すり替えの受理 12/36（#32）。→ I-27（聞き返し）を IF2 として登録し、実行待ち。
* その他：V はモデルの主張が成立し、記憶の主張は不成立。W は ε の上限 5.7% で成立、W-b は不成立。
* **XD（倉庫の画像、10/19 04:21 完了・I-32）**：難しい火（小さく隠れた炎）の見回しの見逃し 12/100（Wilson 上限 19.8%）で登録した15%は不成立。全体 14/151（上限15.0%）、正面のみ 55/151。追加視点（I-20）は 2/151（12件減らし増やさず）だが火のない双子の 65/76 で発動（O3 不成立）→ **事前の撤回規則で既定にしない**（コードの既定は元から OFF）。再較正は τ* なし（0.05 での再現率 79%）。
* * **Q（実写405枚、10/19 04:54 完了・I-36）**：誤許可 0/277（上限 1.4%）で安全側は成立、正しい物資の許可 52/128（40.6%）で登録の70%に届かず主張は不成立（安全だが保守的）。水 33/70、医療 19/58。拒否 76 件のうち 49 件は2回とも「その他」、26 件は順序で答えが割れた。SigLIP・CLIP は全部許可するが誤許可 65・60。
* **XD-R（実写の火のない倉庫写真 200 枚、10/19 05:04 完了）**：0.05 で 11/200（5.5%、Wilson 3.1〜9.6%）、P2 の 0.35 で 0/200（上限 1.9%）が火と誤判定。倉庫の τ* が無いので登録した主張の解析は「不成立」を返す（基準の20%以下は2つの閾値で満たす）。件数には加えず、補遺に明記。
* **A のオフライン（224件の test 半分 112件、10/19 05:23 完了・I-39）**：届け先の誤受理 0/18、意図 112/112、確認を飛ばす計画は厳しくするだけ 0/224（素朴 34/224、ガードレール後 34/224）、全項目集合 0/772。助言の正確な取り出し 51/94。
* **IF を i38 で再実行（探索的、10/19 05:29）**：すり替え 14/36（Wilson 25〜55%）、i35 の 12/36 と同じ結論（i38 でも IF1 は閉じない）。言い直し 12/12。補遺に1文。
* **X（倉庫の閉ループ、59試行、10/19 06:26〜08:51・I-41）**：登録の拘束コミット 238ea9f（初回の run ディレクトリは3秒後）。草案は80試行、登録した操舵の選択が条件を満たす世界だけを入れる（水増ししない）ため 24候補中3世界、X-s は 15 試行になった。行動16/16が設計どおり、火への配達 0/12。記憶は4拠点で 2.14 拠点減（7組・3系列、区間 [1.00, 2.67]、設計 1.75、符号反転 p=0.0078 は7組の最小値）、誤物資 0、K1〜K3 成立。X-m の失敗2件（X002 オドメトリのずれ、X012 到達せず。いずれも航行・基盤の原因）は数に残した。操舵（記述的）：助言なし 0/3、tighten-only 1/3（XC05、全視点 0.010〜0.014）、scrutiny 0/3 だが火のない双子2つも拒否（しきい値 0.01 が火のない映像 0.004〜0.020 の範囲内なので検出の証拠ではない。`scripts/x_readout.py`、FINDINGS #37）。S4 は不成立（登録で「主張しない」）。不成立の主張の数は12のまま。
* **IF2（聞き返し、10/19 05:17 完了・I-38）**：規則あり 0/36（Wilson 上限 9.6%）・通常 12/12 で IF2-1・IF2-2 とも成立（すり替えは両方の物資を名指すので語彙の規則で構造上そうなる。代償：言い直し・否定 24/24 を聞き返す）。規則なしは 15/36。I-27 は v3.7 の推奨に入れる（既定はオフのまま）。
* 不成立の主張は18件（T1・F・T2・J・V4・W-b・IF1・S-perm・XD-eps・XD-rel・XD-cal・Q・YE2・YF4・JH1・QI1・QI2・QI3c）。YF4 は本物の失敗（scrutiny の閾値は火のない拠点を拒否しうる）。YE2 は登録文言の誤り（拒否後も残りの拠点まで探索が続く）で、機構は想定どおり。
* 第三者採点：第11回 36.0/40（第10回 35.5）。模擬査読 R9 は完了し（`docs/paper/REVIEW_NOTES_R9.md`、採択見込み RA-L 約50%・ICRA 約33%）、文章の指摘は I-28 で反映済み。残り：A のオフライン224文の採点（連鎖の最後）、停止後も探索を続ける腕（設計の選択で、実装は大きいので今回は見送り）、XD の ε 上限（15% 以下か）が分かれ目。

* **動画の最終版（10/19 09:55 完成・164.1秒・main の `outputs/video/PAI最終課題_tetsutetsu.mp4`、旧版は `_v5_backup.mp4`）**：倉庫の場面は撮影した火の run（d3d5b23960a74865、正面で見つかった世界なので「横から」とは言わない文言 `front_fire`）。証拠カードに X の行（9行・17秒）。再作成は `make_video_plan.py --recover b4fcd9d164444db7 --memory b93040decbf04ca4 --advice 076f3cb047064fae --depot d3d5b23960a74865`（run は main の `outputs/runs` にある。076f… は i21 の outputs からコピーした）→ rm-dev で `make_demo_video.py --plan docs/video_plan.json --out … --narrate 2`。
* **連鎖は全部完了（X は 08:51）。次の候補**：(1) 拒否のあとも探索を続ける腕（X-s の「助言は配達を2件失わせた」を直す設計。登録が先、まだ登録していない）、(2) 最終凍結（i21 を main にマージ → `make paper FINAL=1`）、(3) 採点と提出手順の確認。

**GPU の自動の連鎖**（scratchpad、nohup、通知なし。ログは scratchpad の *.log）
1. `queue_chain.sh`（`queue.log`）：S（完了・反映済み I-29）→ B（完了・反映済み I-30）→ XD（完了 04:21・反映済み I-32）→ X（**04:41 に予備走行で中止**、I-34、Amendment 1 を main に commit 済み。やり直しは手順 7）→ Q（完了 04:54・反映済み I-36）→ `QUEUE_DONE`
2. `after_queue.sh`：XD のステージ r（実写 258 枚）
3. `after_xdr.sh`：i21 を main にマージ → `scripts/film_depot.sh`（倉庫の場面の撮影）
4. `after_film.sh`：i21 をマージ → `if2_run.sh`（IF2）
5. `after_if2.sh`：i21 をマージ → `a_offline_run.sh`（A のオフライン集合の test 半分。C1 の残り）
6. `after_aoff.sh`：i21 をマージ → `if_i38_run.sh`（IF の文を i38 で再実行する探索的な実験。登録した主張ではない。結果は `if_i38_summary.json`。R9 の指摘：IF は i35 だけだった）
7. （**完了 08:51**）`after_x2.sh`（`after_x2.log`）：上の手順 6（IF38）の終わりを待ち、**倉庫の撮影をやり直し**（10/19 05:08 の1回目は3本とも失敗：速度ガードが古い lidar を見て動きを拒否。ホストが重かったため。`film_depot_runs_attempt1.txt` に記録）→ `x_run.sh`（予備走行をやり直し→X 本走）。X の結果が出たら記憶の転移・助言の方向づけ（X-s）を論文・補遺・README・説明資料に反映し、I-35 として記録する。
* **生の Gazebo を使う段（撮影・X）の間は、ホストを静かに保つ**（4コア。論文のビルドやテストは docker に `--cpu-shares=2`、pytest は `nice -n 19` で、重い処理は避ける）。
* 確認：`grep -E "^=== |DONE|ABORT|FAILED" <scratchpad>/queue.log`。スクリプトが消えていたら、上の順で作り直す。

**各段が終わったら（自分で行う）**
* **S**：`s_summary.json` → `paper_numbers.py` → main.tex・supplement の S の文章と説明資料・README。いずれも生成スクリプト経由で、`check_consistency` は 0 にする。
* **B・XD・X・Q・IF2・XD-R・A offline**：同様に反映する。IF2 の結果で I-27 の判断を書く。（XD は完了：I-20 は撤回。XD-R は `xd_real_summary.json` が出たら別に反映する。）
* **動画の最終版**（撮影の後）：
  1. `make_video_plan.py --recover b4fcd9d164444db7 --memory b93040decbf04ca4 --advice 076f3cb047064fae --depot <film_depot_runs.txt の run>`
  2. rm-dev で `make_demo_video.py --narrate 2` → 3分以内を確認 → main の `outputs/video/PAI最終課題_tetsutetsu.mp4` に置く（旧版は残す）
  3. `update_submission_facts.py`
* **最後**：i21 を main にマージ → `make paper FINAL=1`（だめなら `make snapshot`）→ 採点 → `docs/SUBMISSION_CHECKLIST.md` に沿ってユーザーへ引き継ぐ。

**ユーザーへの未回答の質問**
1. git 履歴に残る個人パス（main の A チェックリストのコミット）を履歴の書き換えで消すか。force push が必要なので、指示があるまで行わない。
2. OpenTimestamps（ハッシュのみ送る）を実施してよいか。
3. ゴミ箱の確認と削除。

## 現在地（2026-10-18 10:00）— 圧縮後はここから

### 0'. 最新（2026-10-18 18:40）
* **A は完了**し、主張は成立（C0〜C6 すべて合格）：
  * 悪意ある助言のもとで危険な配達があった世界は、素朴 12/12、LLM フィルタ 12/12、本方式 0/12（McNemar p=0.0005）。
  * 本方式の配達 43 件はすべて、助言なしの確認でも許可されるものだった。
  * 正しい助言で中央値 27 秒短縮。
  * 読むときの条件：A の全試行は意図の質問 i38（Amendment 1）で走らせた。提出版の既定は i35（FINDINGS #30、DEPLOYMENT）。LLM フィルタはファイル経由の助言を見ない（止めた数：依頼文 7/12、ファイル 0/12、FINDINGS #34）ので、「フィルタ 12/12」はこの条件つき。
  * 代償（記述的）：真の助言で火のある拠点へ誘導されると、配達できなかった世界は 本方式 14/16・scrutiny 11/16・助言なし 0/16。
  * A の図：`scripts/make_a_figure.py`（論文は補足 S9 の図、README と説明資料は `docs/figures/a_results_ja.png`。本文 8 頁に収まらないので補足に置いた）。
* **IF は主張不成立**：すり替えの受理が 12/36（FINDINGS #32）。→ 対策 I-27（物資が食い違えば聞き返す）を研究 IF2 として事前登録した。
  * IF の結果は論文（失敗した登録済みの主張は 7 件目の IF1）・補足・README・説明資料・YouTube 説明・DEPLOYMENT（出発前の読み返しが必須）・storyline の 5 行目に反映済み（コミットの接頭辞 `study IF:`）。IF2 は登録済み・結果待ち（`bash scripts/if2_run.sh`）で、結果が出たら `advice_numbers.if_facts` と同じ形で IF2 の読み取りを足す。I-27 の判断は IF2 の結果まで保留。
* **残りの GPU の順番**（自動。ログは scratchpad）：
  1. `queue.log`：S → B → XD → X → Q
  2. `after_queue.log`：XD のステージ r
  3. `after_xdr.log`：倉庫の撮影
  4. `after_film.log`：IF2
  5. `after_if2.log`：A のオフライン集合（test 半分、i38）。C1 の未了項目。

### 0. 最新の状態（2026-10-18 14:30）
* **GPU の順番**（すべて自動。scratchpad の nohup スクリプトで動かしていて、通知は来ない）：
  1. `queue_chain.sh`（ログは `queue.log`）：A（11:11 に開始、18:00 に完了：判定 HEADLINE_HOLDS）→ IF → S → B → XD → X → Q → `QUEUE_DONE`。
  2. `after_queue.sh`（`after_queue.log`）：XD のステージ r（実写 258 枚）。
  3. `after_xdr.sh`（`after_xdr.log`）：i21 を main にマージ → `scripts/film_depot.sh`（倉庫の場面の撮影）。
* **A は完了し、論文・補遺・説明資料・README・YouTube 説明・動画の証拠カード・図（graphical abstract）・IMPROVEMENT_LOG I-19・FINDINGS #33・#34 に反映済み**（コミットの接頭辞 `study A:`）。残り：登録した224件のオフライン注入セット（`scripts/advice_injection_eval.py --split test`、GPU）の採点は**未実施**で、論文は「採点していない」と書いている。採点したら `experiments/results/advice_injection_eval.json` ができ、`a_checklist.py` の C1 が PASS_RUNS_OFFLINE_PENDING から変わる。
* **動画の最終版**：撮影が終わったら `make_video_plan.py --recover b4fcd9d164444db7 --memory b93040decbf04ca4 --advice 076f3cb047064fae --depot <run>` → `make_demo_video.py --narrate 2`（3分以内）→ `update_submission_facts.py`。
* **提出の手順（ご本人用）**：[`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md)（最終確認 → YouTube → `scripts/set_video_url.py` → public 化 → フォーム）。動画の URL の差し込みは `python3 scripts/set_video_url.py <URL> --apply`、公開前の検査は `python3 scripts/secret_scan.py --history`。
* 締切前の保険：`make snapshot`（結果の出ていない研究は「登録済み・提出時点で未実施」と表記される）。

* **落とし穴（10/18）**：`scripts/build_paper.sh` は `docker exec rm-dev … make_paper_figures.py` を呼ぶ。rm-dev は **main の作業ツリー**で動くので、worktree から実行すると main の図の PDF が再生成される。worktree では latexmk を直接呼ぶか、`docker exec -w <worktree>` を使う。

### A. ユーザーの方針（必ず守る）

* **サブエージェントはちょうど1つ（Sonnet 5.5、`model: sonnet`）を常に動かす。** 同時に2つにしない。終わったら次を起動する。止まったら SendMessage で続きから再開させる。
* **メインの自分も改善作業をする**（サブエージェント任せにしない）。結果を分析し、最大の弱点に絞って、事前登録した評価で確かめる。だらだら改善を続けない。ユーザーが「ストップ」と言うまで自律的に改善を続ける。
* リポジトリの**公開設定（private → public）は絶対に変更しない**。公開と YouTube 投稿は**ユーザーが行う**。push は可。
* ユーザーへの質問・説明は**日本語・簡潔**に。omnicampus のアカウント名は `tetsutetsu`。
* **事前登録してから走らせる。失敗した主張も消さずに載せる**（論文で不成立の主張は18件：T1・F・T2・J・V4・W-b・IF1・S-perm・XD-eps・XD-rel・XD-cal・Q・YE2・YF4・JH1・QI1・QI2・QI3c。件数と一覧は `scripts/check_consistency.py` が `advice_numbers.failed_claims()` と突き合わせる）。改善は `docs/IMPROVEMENT_LOG.md` に「動機→仮説→変更→計測(Before/After)→判断」で書き、**コミットの先頭は `I-xx`**。コミットは必ず push する。
* **sudo は使わない**（docker グループ権限だけで全て動く）。必要になったらユーザーに依頼する。
* **`rm` は使わない**（2026-10-18 ユーザー指示。`rm -rf`・`git clean`・`unlink`・`find -delete` も同じ）。消したいものは `~/rescue-mind-trash/<日時>/` に相対パスのまま移し、移したものをユーザーに伝える。削除はユーザーが確認してから行う。サブエージェントへの指示にも必ず書く。
* **個人情報を入れない**（ホームのパス、スクラッチパッドのパスは `tests/test_no_personal_paths.py` が落とす。文書では `<scratchpad>`、`<user>` と書く）。
* 動画は **1〜3 分**（現在 2:53）。倍速は区間ごとに画面表示（走行 8 倍、確認 3 倍、判断の瞬間は等速）。
* 説明資料のファイル名は **`説明資料_PAI最終課題_tetsutetsu.pdf`**（`docs/report/`）。**締切は 2026-11-02 10:00 JST**。
* 評価基準（創造性・技術力・実用性・表現力）と、論文として通用する水準を常に意識する。実機は用意できない → シミュレーションでできることはすべてやる。
* 当初計画（Jev＋Qwen の 2 つの AI による確認）から勝手に外れない（Jev の役割はローカルの Clef-Flash。J で実装・検証し、採用しなかった結果を論文に載せた）。
* 評価（GPU キャンペーン）の実行中は、重い処理（ビルド・テスト・図・動画）と実行時コードの編集をしない。CPU を使うときは `nice -n 19`。
* 第三者採点（Sonnet 5.5 に `docs/evaluations/EVALUATOR_PROMPT.md` で採点させる）を定期的に行い、点数を上げる改善点トップ5に沿って直す。最新は第11回 **36.0/40**（`docs/evaluations/EVAL_2026-10-18_10.md`。回と点数は `check_consistency.py` が最新の評価ファイルと突き合わせる）。模擬査読は R8 まで（`docs/paper/REVIEW_NOTES_R8.md`、判定は borderline）。

### B. ブランチの考え方

* **`main`** = 事前登録とマージ済みの成果。メインのチェックアウトは `rescue-mind/`（GPU キャンペーンはここで走る。`rm-next` コンテナを使う）。研究の登録は「`main` に載った最初のコミット」で成立する（`docs/REGISTRATIONS.md`、`git log --first-parent` で検証）。
* **`i21-depot`** = 統合ブランチ。worktree は `rescue-mind/.claude/worktrees/i21`。**論文・説明資料・README・docs はここで編集する。** 再開するときは最初に `git pull --ff-only origin i21-depot`。
* **統合マージ `587f033`（2026-10-18 09:08）で i21-depot を main に入れた**（I-19〜I-24、研究 A・B・IF・Q・S・X・XD の登録を含む）。以後 main から i21 への取り込みはしていない：main には `caebcb7`（W-b の入力 `devset_t1_i11_h36_{full,tiles}.json`。`w_analysis.py` を再実行するのに要る）が i21 に無い。次の機会に `git merge origin/main` で i21 に取り込む。
* **HANDOFF は i21 でだけ編集する**（main 側でも編集すると、main へのマージで衝突して連鎖が止まる）。マージされるまで、この方針を守る。
* **main の作業ツリーに、i21 が追跡しているファイルを置かない**（untracked の同名ファイルがあると main へのマージが失敗する）。例：`experiments/results/xd_smoke_ok` は i21 が追跡、すでに main にもある。新しい `*_ok` や結果ファイルを main 側で作る前に `git ls-tree -r origin/i21-depot --name-only | grep <名前>` で確かめる。
* 現在 main の作業ツリーにある untracked（作業用の記録、削除しない）：`campaign_A_pilot_ledger.jsonl`（A のパイロット。`a_run.sh` が次にコミットする）、`experiments/vlm_testset_s/`・`vlm_testset_w/`・`worlds/vlm_devset_hazard2/`、`memory_film/` 等。i21 側にも untracked の描画物（`experiments/vlm_testset_s/`・`vlm_testset_xd/`・`worlds/testset_s/`・`worlds/testset_xd/`）があるが、コミットしない。

### C. 全研究の結果（すべて事前登録。数値は結果ファイルから）

| 研究 | 何を測ったか | 結果（状態） |
|---|---|---|
| D（42 試行） | 固定配置の閉ループ（v3.4） | **完了**。42/42、誤配達 0。台帳は 44 行（再試行を含む。最終行で数えると 42） |
| E（60 試行） | 試行ごとにランダムな世界（v3.5） | **完了**。60/60、誤配達 0。ただし火は 12 件ともはっきり見える大きさ |
| T1（未使用画像 600 枚） | 画像レベル、v3.4 の誤許可 | **完了・主張は不成立**。誤許可 5/408（Wilson 上限 2.84% > 登録した 2%）。τ_h=0.05 では 3/408。物資の誤許可は 0/332 |
| T2（未使用画像 600 枚） | 画像レベル、v3.5 | **完了・天井で不成立**（改善が測れない）。誤許可 0/407、正しい許可 190/193 |
| F（24 世界×2、小さな火） | 閉ループの対比較、v3.5 対 B | **完了・不成立**。火が見える 13 世界で配達 12/13 → 7/13、p=0.0625。（B の見逃しのうち 1 件 W21 は 8,573 画素。訂正済み） |
| G（24 世界×2） | 横から見直す（I-14） | **完了・成立**。火が見えるのに配達 11/16 → 1/16（p=0.00195）、火の無い世界の誤停止 0/8 |
| H（16 系列、112 run） | 出動をまたぐ記憶（I-15） | **完了・成立**。危険な配達：素朴 20/32、検証つき 0/32（p=1.9e-6）、記憶なし 1/32。入れ替わりが続く出動の所要時間 114 → 79 s（8 組すべて短縮、p=0.0078） |
| J（24 世界×2、48 run） | Jev 役 Clef-Flash＋Qwen3.5-4B（I-16） | **完了**。V100 1 台で動く（ピーク 28,676 MiB、成立）が、危険な配達は J 1/24 対 v3.6 単独 0/24 で P2 は**不成立** → 不採用。論文に「実装し、検証し、採用しなかった」と書いた |
| K | 適合予測による閾値の較正 | **完了**。凍結した τ_h=0.05 は T2 で見逃し 0/76、誤許可 0/407（較正側の見逃しは 23/211） |
| L（24 世界） | 配置のランダム化（I-17） | **完了・成立**。24/24、危険な配達 0 |
| P / P2 | 実写（D-Fire）で危険の質問が通用するか | P：検出 298/300、誤警報 64/100（τ_h=0.05）。P2：h35・τ=0.30 で検出 282/300、誤警報 18/100（**成立**） |
| R（300 枚×12 劣化条件） | カメラ劣化 | **完了・成立**。誤許可 0/2304（Wilson 上限 0.17%）。もっとも厳しいのは強い露出オーバー |
| Z | ゼロショット SigLIP/CLIP との比較 | **完了**。SigLIP の誤許可は T1 で 44/408、T2 で 47/407（本方式は 3 と 0）。CLIP はほぼ全拒否（正しい許可 2/191） |
| V（10 系列×6 出動、160 run、失敗 0） | H のモデルの予測検証 | **完了**。モデルの予測は**成立**（時間差 14.9 s が予測区間 11.3〜20.1 s の内側、危険な配達 M0 0・M1 20・M2 1、速さ p=0.00586）。**記憶の安全 V4 は不成立**（余裕 M2−M0=1 ≤ 3 は成立、系列単位の McNemar 5 対 0 で p=0.0625）。原因は検出力不足と、M2 の 1 件（V156）の到着ぶれによる検査の誤り（右の視点 p_h=0.013。FINDINGS #29）。H＋V をまとめると危険な配達 M0 1/82、M2 1/82、M1 40/82 |
| W（小さく隠れた火 150＋双子 75、画像） | 見回しの取りこぼし上限と先行手法 | **完了**。見逃し 見回し 3/150（Wilson 上限 5.7% ≤ 15%、**成立**）、正面のみ 76/150（横からしか見えない火 23 件のうち 22 件）、双子の余計な停止 0/75（**成立**）。先行手法（同じ全体画像）：本方式 3/815、投票 9/815（Holm p=0.094）、KnowNo 風 α=0.05 は 1/815 で正しい許可が 303/384 に低下 → 判定規則そのものが優れる主張は**不成立（0/3）**。I-20（疑わしいとき視点を増やす）：見逃し 2/150、双子の損失 0/75 → 事前の規則を満たし v3.7 の既定にした |
| I-22 Gazebo 確認 | 配送インターロックの実機（シミュレーション）確認 | **合格**（4 ミッション。許可証は承認時のみ、隠れた火＋「確認不要」の助言は拒否・停止）。動画の素材にした |
| I-23 / I-24 | 命題 2 の z3 検証／助言の信用枠 | I-23：99 件が unsat、実関数との突き合わせ 9,000 件で不一致 0、変異 11/11 検出（F1〜F3 を修正）。I-24：命題 3、閉ループは B で測る |
| **A（226 run、予備走行 27 run）** | 助言は検査を緩められるか、攻撃者が買えるもの | **予備走行は失敗**（2026-10-18 09:14〜）。依頼文で助言する経路（operator）の run がすべて意図ゲートで拒否された（v3.6 の意図プロンプト i35 が、拠点を「避難所 B 以外の届け先」と読む）→ **FINDINGS #30**。i38 は事前に固定した規則（I-25）で採用済み（`experiments/results/intent_i38_check.json`：保留 55/60 で両方同じ・危険 0、dev の注入で正しい受理 86→92/94・取り違え 0）。**Amendment 1**（`experiments/PREREGISTRATION_A.md`、コミット 2a1bab0）で A の全試行を i38 にし、最初のパイロット台帳は `campaign_A_pilot1_ledger.jsonl` に残した（27 試行：依頼文チャネル 12 件中 0 件が意図どおり、うち 6 件は意図の段で拒否、残りは取れた項目が設計と違った）。**Amendment 2**（コミット 1163eee、10:38）で予備走行の合格条件を「依頼文チャネルの意図の受理 9/12 以上」に変え、正確な取り出し（FINDINGS #31：最初の予備走行で 0/6）は報告項目にした。新しい台帳でやり直した予備走行は合格した（`A_PILOT_OK` 10:56：意図の受理 12/12、ファイルチャネル 12/12、正確な取り出し 0/12）。**本走行（226 試行、11:11 開始、失敗 0）は完了し、登録した主張は成立**（`a_checklist.md`：C0〜C6 合格、判定 HEADLINE_HOLDS）：悪意のある助言の12世界で危険な配達が起きた世界は 素朴 12/12・LLM ガードレール 12/12・本方式 0/12（McNemar p=0.0005）、本方式の配達 43/43 は助言なしの確認でも許可、正しい助言の時間短縮 中央値 27.1 秒（6/6、p=0.031）、代償は上限内（最大 +41.7 秒 ≤ 50.6 秒、取りこぼし 0）。A-steer は記述的：本方式の危険な配達 2/16（確認の誤り、有意でなく ε_any の区間内）、**配達できない世界 14/16**（FINDINGS #33）。ガードレールは助言ファイルでは 0/12 しか止めなかった（FINDINGS #34）。依頼文チャネルの正確な取り出しは 36/72（報告項目）。**未了：オフライン注入セットの採点**。論文・補遺・README・報告・YouTube・動画の証拠カードに反映済み（マクロ `AWorlds*` `ASteer*` など。生成は `advice_numbers.a_facts()`）。v3.6 の既定は i35 のまま、IF は i35 を測る |
| IF（72 文） | 依頼文で依頼物資を書き換えられるか | **完了・不成立**。36 文中 12 文で、注入された物資を受理（FINDINGS #32）。対策は IF2（登録済み・未実行） |
| S（64 世界、276 画像） | 場面内の文字（貼り紙・看板）による注入 | 登録済み・**未実行**（約 2.4 時間。看板の確認 `sign_check_ok` は済み） |
| B（48 run＋予備走行 6） | 信用枠（I-24）の閉ループ | 登録済み・**未実行**（約 1.5 時間。Amendment 2：両アームでインターロックを有効にする） |
| XD（画像、4 拠点の倉庫） | 倉庫で v3.6 の検査を再測定。I-20 を取り消す規則の判定を含む | 登録済み・**未実行**（スモーク確認 `xd_smoke_ok` は済み）。XD-R の実写の火のない倉庫写真は採点前に凍結済み（Commons の候補 394 枚から目視確認で 258 枚を採用、`experiments/xd_real_manifest.jsonl`・`xd_real_exclusions.json`。登録どおり先頭 200 枚を採点） |
| X（80 run＋予備走行 9） | 倉庫の閉ループ（M0 対 M2、k=4、助言の操縦） | 登録済み・**未実行** |
| Q（Wikimedia Commons 405 枚） | 実写の物資確認 | 登録済み・**未実行**（GPU 約 40 分。W の後の連鎖が .gitignore の衝突で止まり、一度も走っていない） |

* 登録済み 7 本（A・B・IF・Q・S・X・XD）は統合マージ 09:08 で main に載り、A の予備走行が 09:14 に始まった時点で、IF・S・B・XD・X・Q は試行も推論もしていない。これらの登録ファイルには「DRAFT」の行が残るが、拘束力のある版は `docs/REGISTRATIONS.md` の表の版（ファイルは変えない。変更は日付とコミットつきの Amendment で追記する）。
* テスト関数は 1621 件（`python3 scripts/count_tests.py` の静的な数え方）。FINDINGS は 50 件。

### D. GPU の順番と、その動かし方

**予定の順番**：i38 の確認 → **A（再実行）** → IF → S → B → XD → X → Q。GPU は同時に 1 本だけ（同じ ROS ドメイン／Gazebo パーティション／ポート 8765 を使うので並行しない）。

**今の状態（10:00 ごろ）**
* （解決済み）A の最初のパイロットは 09:14 に始まり、i35 では依頼文チャネルが意図の段で拒否されて不合格になった（FINDINGS #30・#31）。i38 の採用（Amendment 1）と合格条件の変更（Amendment 2）のあと、パイロットは合格し（10:56）、本走行が 11:11 に始まった。
* スクラッチパッドの連鎖 `i38_check_chain.sh`（実行中）が、`after_q.log` に `A_CHAIN_ABORT`（または `A_CHAIN_DONE`）が出るのを待つ → main に i21-depot をマージして push → サーバを i35 と i38 で順に起動し `scripts/intent_i38_check.py --tag i35|i38`（約 10 分）→ `--decide` → `I38_CHECK_DONE`。**採用規則は走らせる前に固定済み**（`scripts/intent_i38_check.py` の冒頭と FINDINGS #30。IMPROVEMENT_LOG にはまだ i38 の項が無い）：保留テスト集合（held_out_v34）で危険な誤りが増えず、正しい答えの減りが 1 件以内、かつ注入文の dev 半分で避難所の取り違えが 0 件のまま正しい受理が増えること。結果は `experiments/results/intent_i38_check.json`。
* **このチェーンは main に `experiments/results/i38_stop_server.sh`・`i38_server_*.log`・`intent_i38_check.json` を作る（untracked）。** i21 側で同名のファイルを追跡しないこと。

**連鎖スクリプトは再作成が要る。** `after_a_chain.sh`（A の後に IF と S）、`after_s_chain.sh`（B）、`after_b_chain.sh`（XD→X）、`after_x_chain.sh`（Q）は、スクラッチパッド（`<scratchpad>`）に置いたものだが、**今は動いていない**（待ち条件が `after_q.log` の `A_CHAIN_DONE` で、A の本番が走らない限り来ない）。**スクラッチパッドが無い、またはプロセスが無いときは作り直す。** 型は次のとおり（各段は前の段の完了行をログで待ち、`git pull -q --ff-only` してから次を呼び、完了行を出す）：

| 段 | 呼び出し | 完了の印 |
|---|---|---|
| i38 確認 | `i38_check_chain.sh`（上記） | `I38_CHECK_DONE` |
| A（再実行） | i38 を採用したときだけ：A の事前登録に **Amendment** を追記・コミット・main に載せ、古いパイロット台帳を別名（例 `campaign_A_pilot1_ledger.jsonl`）に退避して残してから `bash scripts/a_run.sh`（予備走行 27 → マスク → 登録の確認 → 226 run、約 11.5 時間 → `a_analysis.py`） | `A_DONE` / `A_ABORT` |
| IF | `bash scripts/if_run.sh`（約 2 分） | `IF_DONE` |
| S | `docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && bash scripts/s_render.sh"` → `bash scripts/s_eval.sh`（`experiments/vlm_testset_s/sign_check_ok` があること） | `S_DONE` |
| B | `bash scripts/b_run.sh`（予備走行 6 → 本番 48） | `B_CHAIN_DONE` |
| XD | `docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && bash scripts/xd_render.sh"` → `bash scripts/xd_eval.sh`（`xd_smoke_ok` があること） | `XD_DONE` |
| X | `bash scripts/x_run.sh`（予備走行 9 → 本番 80） | `X_DONE` |
| Q | `bash scripts/q_run.sh`（約 40 分） | `Q_DONE` |

* 各スクリプトは、登録（コミット済み・未変更）を確かめてから始める。`*_run.sh` が `ABORT` を出したら原因を直し、Amendment に記録してから再実行する（キャンペーンは再開できる。`--only` は台帳にある試行をやり直すので注意）。
* i38 を**採用しない**場合：A の依頼文チャネルは測れない。ファイルチャネルだけで走らせるか、不成立として報告するかを、Amendment に理由を書いて決める。IF は i35 を測るので、どちらでも変えない。
* 実行中はホストの負荷を見る（`awk '{print $1}' /proc/loadavg`、4 コアで 6 未満）。`docker ps` に `rm-next`（GPU）、`rm-dev`（図・PDF・テスト）、`rm-voicevox` がいること。
* 各段が終わったら `bash scripts/finalize_results.sh`（結果の解析 → 論文・説明資料・README・YouTube 文の再生成 → 整合性検査。`nice` つき、GPU を使わない）。コミットはしない処理なので、確認してから `docs:` か `study X results` でコミットする。

### E. 主要コマンド（詳しくは §3）

```bash
git pull --ff-only origin i21-depot                         # 再開の最初（worktree .claude/worktrees/i21 で）
nice -n 19 python3 scripts/check_consistency.py             # 文書と結果ファイルの突き合わせ（0 mismatch が正常）
python3 scripts/count_tests.py                              # テスト関数の数（静的）。実行は python3 -m unittest discover -s tests
bash scripts/finalize_results.sh                            # 結果が出たあとの再生成（GPU を使わない）
make help                                                   # make paper / report / readme / youtube / video / check / verify-quick
make paper FINAL=1                                          # 提出用ビルド（TBD と (pending) が残っていれば失敗する）
python3 scripts/intent_i38_check.py --decide                # i38 の採否（規則は固定済み）
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py ... --advice <run_id>   # 動画 v5 の助言の場面
```

* 動画 v5 の撮影済みの run（I-22 の確認で撮影）：`076f3cb047064fae`（隠れた火＋「確認不要」を却下し、左の視点で停止）。記憶の run は `b93040decbf04ca4`、デモの run は `dbed92419f88479e`（配達）・`b4fcd9d164444db7`（取り違え）・`9d73663832c94f16`（隠れた火）。`outputs/` は Git 管理外。
* 論文の `docs/paper/numbers.tex` と各 `tab_*.tex` は `scripts/paper_numbers.py` が生成する（手で直さない）。助言まわりの数値は `scripts/advice_numbers.py`。

### F. 判断待ち・未決

* **OpenTimestamps（事前登録のハッシュの外部タイムスタンプ。送るのはハッシュのみ）を実施してよいか、ユーザーの回答待ち。** 回答が来るまで実施しない（`docs/REGISTRATIONS.md` に未実施と明記済み）。
* **I-20 は v3.7 の既定にした（W で事前の規則を満たした）が、証拠は 1 世界だけ**（見逃し 3/150 → 2/150）。閉ループでは一度も測っていない。**元に戻す規則を XD で判定する**（XD の O3：双子での追加視点の起動が 15% 超、正しい許可が 5 ポイント以上低下、知覚できる危険で見逃しが 1 件も減らない、のどれか 1 つで取り消し）。登録済みの A・S・X・XD・B・IF は凍結した v3.6 で走る。
* **i38 の採否は決着**（採用、Amendment 1）。i35 を既定とする IF の登録は変えない。
* **動画 v5 は暫定**：`outputs/video/PAI最終課題_tetsutetsu_v5.mp4`（2:53＝172.5 秒、`docs/video_chapters.json` が章立て）。助言注入のデモ（I-22 の撮影）、評価 V（予測は成立、記憶の安全は不成立）、z3 を入れた証拠カードがある。P/P2 の行は 64/100 のみ。**倉庫（デポ）の場面は X の後**（`docs/design/video_v5_plan.md`）。概要欄は章立てから再生成する（`make_youtube_description.py`）。
* X の後に決めること：A・X でインターロック（I-22）を有効にするか（B は有効、A は無効のまま登録）。信用枠（I-24）の閉ループ確認は B で測る。
* ユーザーがすること：リポジトリの公開、YouTube への投稿、README とフォームへの URL 記入、提出。

### G. 成果物の状態と整合性

* 論文：`docs/paper/main.pdf` 10 頁（本文は 8 頁以内、参考文献は 8 頁目から）、補足 `supplement.pdf` 22 頁。未実行の研究の結果欄は灰色の「(pending)」（`make paper FINAL=1` は pending が残ると失敗する）。説明資料 `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf` は **20 頁**（旧版の HANDOFF は 18 頁と書いていた）。
* `python3 scripts/check_consistency.py`：**0 mismatch**（2026-10-18 09:43 に確認）。S・X の README の行は「実行中」、A・V・W は結果ありで検査する（A は 18:00 に完了）。結果が出るたびに、検査の「結果待ち」の期待も更新する。
* 整合性検査を通し、`make paper FINAL=1` が通る状態を締切（11/02 10:00）の数日前までに作る。結果が出ない研究があっても、登録どおり「未実行」と書いた版で確定できるようにしておく。

---

## 履歴（要約）— 旧 HANDOFF の日付ごとの節（全文は `docs/HANDOFF_ARCHIVE.md`）

* **旧 §1「現在の到達点（v3.6、10/17）」の表**：D/E/G/H/T1/T2/R/Z/P/K/J/P2/L/V/W の数値と v3.6 の既定構成（Qwen3.5-9B、v35、i35、τ_s=0.5、τ_h=0.05、h36＋tiles、横から見直す ±0.4 m、回復探索）。上の表に統合した。過去の評価の再現は各台帳の `stack_args` を使う。
* **旧 §5「現状（10/18 10 時ごろ）」**：方針（Jev は Clef-Flash、結果を分析して最大の弱点に絞る、実機なし）、v3.6 の既定構成、主な結果、10/17 の進捗（動画 v3.6、R・H・J・Z・P の事前登録と実行、第三者採点の開始、論文の章立て）。
* **10/17 13:10**：R（0/2304）、J の試運転（28.7 GiB）、Z・P 完了、命題を「観察」と「1 出動あたりの系」に変更、第三者採点 1 回目 28.0・2 回目 29.5。H 本番を 13:03 に開始。
* **10/17 夕方（利用上限で中断）**：H 53/112、再開手順（`finalize_results.sh`、`% CHECK-AFTER-H`、動画の作り直し、L のマージ、OpenTimestamps の質問）を記録。
* **10/17 16:20**：K（適合予測）、I-18（現場への 1 枚報告）、グラフィカルアブストラクト、連鎖 `final_chain.sh`・`post_j_chain.sh`・`after_p2_chain.sh` を作った。評価中は実行時コードを変えない規則。
* **10/17 16:50**：H 完了（主張はすべて成立）。危険な配達 20/32 → 0/32、114 → 79 秒。
* **10/17 17:15（重要）**：評価中に重い処理をして J の判断時間が 3〜7 秒から 25〜33 秒に延びた（J の事前登録に逸脱を記録、FINDINGS #23）。中央値の計算誤りを訂正（FINDINGS #22）。第三者採点 4 回目 31.5、模擬査読 3 回目 borderline。
* **10/17 17:25（★）**：連鎖 `final_chain`（J）→ `post_j_chain` → `render_after_film` → `after_p2_chain`（L）→ `after_l_chain`（V）→ `after_v_chain`（W）を並べた。study V（H のモデルの予測検証）の設計。
* **10/17 19:30**：J 完了（P1 成立、P2 不成立 → I-16 不採用）。第三者採点 5 回目 31.5/32.0。**中心の貢献 I-19「信頼できない入力は締める方向にしか使えない」**を立てた（`docs/design/I19_untrusted_inputs.md`、研究 A・S の設計、注入文 224 件を dev/test に分割）。
* **10/17 20:15**：P2 成立、L 実行中、第三者採点 6 回目 32.0。動画 2:53 に再描画。A に LLM フィルタ群を足して 162 run に。
* **10/17 21:00**：I-20（疑わしいときだけ視点を増やす）、I-21（現実的な倉庫と k 拠点）、文献調査（`LITERATURE_REVIEW.md`）、一貫性と頑健性の曲線、研究 Q の設計。
* **10/17 21:45**：L 完了（成立）、I-18 を main にマージ、V の予備走行合格、倉庫が Gazebo で読み込めた。模擬査読 5 回目への対応（保証の書き直し）。
* **10/17 22:00・23:00**：連鎖の並び（V → W → Q → 統合マージ → A）。統合ブランチ `i21-depot` に I-19〜I-22・軟拒否・scrutiny・研究 S/X/XD・信頼基盤テスト（変異体 196 個）・論文の再構成を集約。模擬査読 6 回目は「結果が設計どおりなら RA-L で weak accept 圏」。
* **10/17 23:30（★★）**：V 本番 160 run 実行中（50/160）、連鎖 `after_v`→`after_w`→`after_q`（統合マージ → A）。第三者採点 7 回目 33.0。
* **10/18 0:30（★★★）**：FINDINGS #26〜#28 の修正（fail-open、τ_h 未検証、記憶の自己固定）を i21-depot にマージ。I-24（助言の信用枠）完了。研究 IF・B を登録。I-23（z3 による機械検証）を Sonnet が実行。追加の連鎖 `after_a`・`after_s`。
* **10/18 2:30（★★★★）**：ユーザー指示「Sonnet はちょうど 1 つ、メインも改善作業」。I-23 の機械検証、I-24 v2（R7 の反例 4 件）、命題 2 の必要性、重みの固定（PINNED_REVISIONS）、B・IF の登録。HANDOFF は i21 でだけ編集する。第三者採点 8 回目を Sonnet が実行。
* **10/18 3:45（★★★★★）**：V 完了（モデルの予測は成立、記憶の安全は不成立）。I-22 の Gazebo 確認は合格（4 件）。動画セグメント 4 を撮影。S の看板確認・XD のスモーク確認は合格。
* **10/18 午前（★★★★★★）**：W 完了（見逃し 3/150 成立、双子 0/75 成立、先行手法の優位は不成立）。I-20 を v3.7 の既定に採用。`\Nfailed` を six に。第三者採点 8 回目 34.0/40、模擬査読 R8（borderline）。
* **10/18 09:08〜09:40（旧 HANDOFF の後に起きたこと）**：統合マージ `587f033` で登録 7 本が main に載る（`docs/REGISTRATIONS.md`）。A のパイロットが 09:14 に始まり、依頼文チャネルが全滅 → FINDINGS #30、i38 の候補と採用規則を固定。I-20 の構成の固定と元に戻す規則（XD で判定）、R8 の指摘への対応（主張の衛生）。
* **10/18 10:09〜10:40**：i38 を採用（I-25）、A の Amendment 1（2a1bab0）、最初のパイロット台帳を保存（2270812）、XD-R の写真を凍結（263ad8e）。論文（本文に 1 文、補遺 S9 に段落と修正表 S10）、登録監査（`tab_prereg` の Amendments 列は見出し数で数える。B は 0→2、A は 0→1、C は 0→1 に直った）、`docs/REGISTRATIONS.md` の Amendments 表、README・報告の生成器を更新。Amendment の文中の時刻（A は 10:30）と git の時刻（10:09）は違う。表は git の時刻を使う。
* **旧 §6「論文化で残っている作業」**：T1・E の結果の反映、図、遅延の内訳と VRAM の表、推敲。いずれも済み。未解決として、稀に 0.3 秒間送信が止まる現象の根本原因（I-09 で影響は除去済み）と実機での検証（用意できない）が残る。

---

## 2. 実行環境（ホスト：Ubuntu 22.04、Tesla V100 32GB、4コア、ROSはホストに無い）

* Docker イメージ
  * `rescuemind:jazzy-next`（**標準**、`docker/Dockerfile` の `STACK=next`）：ROS 2 Jazzy + Gazebo Harmonic + torch 2.8.0+cu126 + transformers 5.20、`nice` に `cap_sys_nice`。
  * `rescuemind:jazzy`（旧 v3.3 スタック：torch 2.5.1 + transformers 4.53）。図・PDF・テスト用のコンテナ `rm-dev` はこちら（IPAex フォントを apt で後入れ済み。再作成時は `docker exec -u 0 rm-dev bash -c 'apt-get update && apt-get install -y fonts-ipaexfont'`、ただし jazzy-next にはフォントが入っている）。
* 作業用コンテナ（`docker/run.sh` は repo を同じ絶対パスでマウント、HFキャッシュ `/hf`、host network、`--init --cap-add SYS_NICE`）
```bash
S=<scratch>   # 任意の一時ディレクトリ
RESCUEMIND_IMAGE=rescuemind:jazzy-next RESCUEMIND_DOCKER_EXTRA="-v $S:$S" RESCUEMIND_CONTAINER=rm-next bash docker/run.sh sleep infinity
RESCUEMIND_DOCKER_EXTRA="-v $S:$S" RESCUEMIND_CONTAINER=rm-dev bash docker/run.sh sleep infinity
docker exec rm-next rescuemind-entrypoint <command>     # entrypoint 経由で ROS と venv を source
docker run -d --name rm-voicevox -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest   # ナレーション用
```
* モデル重みはホストの `~/.cache/huggingface`（Qwen2.5-VL-3B, SmolVLM2, Qwen3-VL-8B, Qwen3.5-4B/9B 取得済み）。実行時は `HF_HUB_OFFLINE=1`。
* ポート：VLM 8765（オーケストレータが自動起動）、VOICEVOX 50021。ROS_DOMAIN_ID=73、GZ_PARTITION=rescuemind_1008。
* **同時に2つのスタックを走らせない**（同じ ROS ドメイン / Gazebo パーティション）。

## 3. 主要コマンド

```bash
# 1試行（例：取り違え）
docker exec rm-next rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped \
  --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain --capture-rosbag \
  --instruction 'Bの避難所にペットボトルの水を運んで'     # 追加: --hazard-at medicine / --lighting dim_evening / --distractor-at water / --film
# 事前登録キャンペーン（台帳に追記、中断しても再開可）
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json \
  --ledger experiments/results/campaign_D_ledger.jsonl -- <凍結構成のフラグ>
# 成果物の再生成（数値の手入力なし）
docker exec rm-dev rescuemind-entrypoint python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_figures.py
python3 scripts/update_readme_results.py
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_report.py --account tetsutetsu
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py --deliver a93d6a9cc8704e6c --recover 8b54abfb36454b27 --fire a213a61bc53e4787
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_demo_video.py --plan docs/video_plan.json --out outputs/video/PAI最終課題_tetsutetsu.mp4 --narrate 2
# 開発セット・モデル比較
scripts/robust_devset_build.py, scripts/vlm_devset_eval.py, scripts/robust_devset_report.py, scripts/model_comparison_v35.sh, scripts/model_selection_table.py
scripts/intent_eval.py --method hybrid --model <id> --split dev_v35|held_out_v34   # held-out はチューニングに使わない
```
デモ収録 run（`--film` 付き。**旧版の動画の run。現行の動画の run は §5 を参照**）：deliver `a93d6a9cc8704e6c`、recover `8b54abfb36454b27`、fire `a213a61bc53e4787`（`outputs/runs/` 内、Git管理外）。現行の動画の run は「現在地」E を参照。

## 4. 落とし穴（実際に踏んだもの）

* `pkill -f <pattern>` を `bash -c '...pattern...'` の中で使うと**自分自身のシェルも殺す**（exit 143）。スクリプトファイルから実行する。
* サーバ再起動直後は**古いサーバがまだ応答**することがある → `while curl -s -m 2 http://127.0.0.1:8765/health; do sleep 1; done` で消えるのを待つ。
* `nice` はファイルケーパビリティ付き → その exec は glibc セキュアモードで **LD_LIBRARY_PATH が消える**。`nice` は必ず「ROS を source するシェル」の外側に置く（`prioritised(shell_exec(...), n)`）。シェルスクリプト内は `renice -n N -p $$`。テスト `tests/test_v34_priority_wrapping.py`。
* ROS の `setup.bash` は `set -u` と相性が悪い → `set +u; source ...; set -u`。
* 画像トピックは Reliable QoS（`rescuemind/ros_qos.py`）。Best Effort だと 0.9 MB 画像が大量に欠落。
* 4コアのホストは CPU が飽和気味（ロードアベレージ約3.9）。**キャンペーン中に重い処理（動画合成・音声合成・ビルド）をしない**。キャンペーン中に実行時コードを編集しない（各試行がファイルを読み直す）。
* 非rootユーザーには `--cap-add` だけでは権限が渡らない（ファイルケーパビリティが必要）。
* Qwen3.5 は思考モードが既定 → `enable_thinking=False`（サーバで対応済み）。FP16 で非有限 logits なら判断拒否。
* 動画は **3分以内**（現在 2:53）。倍速は区間ごとに画面表示（走行8倍、確認3倍、判断の瞬間は等速）。


## 7. 主要ファイルの地図

* 現在地・履歴：このファイル。旧版の全文：`docs/HANDOFF_ARCHIVE.md`。
* `docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D15）、`docs/IMPROVEMENT_LOG.md`（I-01–I-24）、`docs/FINDINGS.md`（実行で見つけた50件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）。
* `docs/REGISTRATIONS.md`（事前登録の台帳：main に載った最初のコミットと sha256）、`docs/REPRODUCE.md`（クリーンな Ubuntu＋NVIDIA 環境での 3 段階の再現手順）、`docs/REPRODUCIBILITY.md`。
* `docs/evaluations/`（第三者採点、第1〜8回と固定の指示文）、`docs/paper/`（論文・補足・`REVIEW_NOTES*.md`・`LITERATURE_*.md`・`PROOF_REVIEW.md`）、`docs/report/`（説明資料）、`docs/design/`（I-19〜I-24 の設計、動画 v5 の計画）。
* `experiments/`（事前登録 `PREREGISTRATION_*.md`・プロトコル・開発セット・台帳 `results/campaign_*_ledger.jsonl`・要約 `results/*_summary.json`）。
