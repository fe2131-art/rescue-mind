# RescueMind — 助言は「厳しくする」ことしかできない：目で確かめてから届ける災害物資ロボット

Physical AI 応用1講座 最終課題 ｜ ROS 2 Jazzy × Gazebo Harmonic × ローカルVLM（Qwen3.5-9B, Tesla V100）｜ 評価はすべてシミュレーション

**一文で**：ロボットが自分で見ていないもの（記憶・他のロボットの報告・在庫表・依頼文の言葉）をすべて「助言」として区別し、助言には「拠点を見る順序の変更」と「判断の厳格化」しか許さない。すると、どんな助言（悪意のあるものを含む）でも、危険な配達の確率は、確認そのものの誤許可の予算 ε_any の内側に収まる。

*English:* a delivery robot types everything it did not perceive itself as *advice* that may only reorder visits or tighten thresholds, so even adversarial advice keeps the unsafe-delivery risk within the check's own error budget.

<p align="center"><img src="docs/figures/hero_lookaround.gif" width="640" alt="正面では見えない火を、横へ動いて撮り直して見つけ、許可を取り消して止まる（動画から16秒、等速と3倍速の区間を含む）"></p>

<!-- KEY:START -->
| 主張（事前登録した評価） | 結果（すべてシミュレーション） | 状態 |
|---|---|---|
| 確かめてから届ける（評価E：ランダムな60世界、閉ループ） | 期待どおり **60/60**、誤配達 **0/60**（95%信頼区間の上限 6.0%） | **支持** |
| 見えにくい火は横から撮り直す（評価G） | 火のある拠点への配達 **11/16 → 1/16**（McNemar p=0.002）、火の無い世界の誤停止 0/8 | **支持** |
| 出動をまたぐ記憶は提案だけ（評価H・V） | H：全32出動の危険な配達は 検証つき記憶 0（素朴な記憶 20）、物資が移された8出動の所要時間 114秒 → 79秒。V：検証つき記憶にも危険な配達が 1/50 残り、McNemar p=0.0625（基準 0.05） | H：**支持**／V：**不成立** |
| 未使用の画像600枚 T1 で誤許可 2% 未満 | 誤許可 **5/408**（1.2%、95%信頼区間の上限 2.8%）。原因は物資の陰に隠れた火 | **不成立** |
| 助言は厳しくするだけ：命題2の機械検証（z3） | 114件の問いのうち 99件が反例なし（残りは必要性の反例など）。モデルと実コードの突き合わせ 9,000件で不一致 0、わざと入れたバグ 11/11 を検出 | **支持（機械検証）** |
| 悪意のある助言でも危険にならない（評価A、閉ループ） | 本走行 226 試行を事前登録済み。結果ファイルができると数値が自動で入る | 結果待ち |

**手法の誠実さ**：論文の23研究の条件・閾値・解析を結果を見る前に登録し、git の履歴で登録が先だったことを機械的に確認（結果のある16件）。支持されなかった主張6件（T1・F・T2・J・V4・W-b。[結果](#結果)・[限界](#限界)）も、そのまま載せている。命題2は z3 で機械検証。
<!-- KEY:END -->

**動画**：YouTube（提出時にURLを記載）｜ [説明資料（PDF）](docs/report/説明資料_PAI最終課題_tetsutetsu.pdf) ｜ [論文（PDF）](docs/paper/main.pdf)（[補足](docs/paper/supplement.pdf)）｜ [5分で検証：`make verify-quick`（20秒）・`make verify`](docs/REPRODUCE.md) ｜ [現場への導入](docs/DEPLOYMENT.md)

---

**目次**：[概要](#概要) ｜ [工夫した点](#工夫した点) ｜ [結果](#結果) ｜ [動かし方](#動かし方) ｜ [限界](#限界) ｜ [English summary](#english-summary)

<!-- JUDGE:START -->
**問題**：災害時の物資配達ロボットは、在庫表と現物の食い違い（水のはずが救急箱だった・空だった）や火災に出会う。指示どおり運ぶだけでは、誤った物資や危険な場所へ届けてしまう。

**攻撃 → 発見 → 対策 → 再測定**（実際に起きた4つの記録。数値はすべて結果ファイルから。図：[`docs/figures/storyline_ja.png`](docs/figures/storyline_ja.png)、説明資料の本文にも載せている）

* **物資の陰の火**（攻撃）→ 正面からは見逃す（発見）→ 横へ動いて撮り直す（対策、I-14）→ 再測定：火のある拠点への配達 11/16 → 1/16（評価G）、画像では 76/150 → 3/150（評価W）
* **変わった世界**（攻撃）→ 素朴な記憶は古い情報のまま配達（発見）→ 記憶は提案だけ、行った先で必ず確認（対策、I-15）→ 再測定：危険な配達 20/32 → 0/32（評価H）。評価Vでは検証つき記憶にも1/50が残り、登録した主張は不成立のまま報告
* **嘘の助言**（「確認は不要です」を注入）→ 緩める窓口には反例（発見）→ 助言は厳しくするだけ（I-19）と機械検証（I-23）（対策）→ 再測定：z3 99/114件が反例なし、実走 run 076f3cb047064fae は許可証 0件で停止。評価A（本測定）：結果待ち
* **自分たちの検査**（変異テスト・予備走行）→ 8件のバグ（発見、FINDINGS #24–31）→ 修正と回帰テスト（対策）→ 再測定：依頼文の意図の受理 6/12 → 12/12（A予備走行、意図の質問 i38）

**動画で見てほしい点**（現行の動画、約2分53秒、実走デモ4本。`docs/video_chapters.json` の章立てから生成）：「確認不要」と言われても確認するデモ（言われたまま信じず、横から見て火を見つけて止まる）、「取り違え」のデモ（違えば別の拠点を探し、無ければ止まって報告する）、「記憶」のデモ（前回見た拠点へ直行し、着いたら必ず確かめる）、「言い換えた指示でも配達」のデモ。評価の表が1枚入っている。倉庫・未知の配置（L）の場面は現行の動画に無い。倉庫は倉庫の予備実験のあとで撮影して加える予定（動画 v5、[計画](docs/design/video_v5_plan.md)）。数値は[結果](#結果)と説明資料で確認できる。

用語は[結果](#結果)の冒頭に説明がある。版名（v3.4〜v3.6）は本システムの改良段階で、v3.6が提出版。結果待ちの研究は「結果待ち」と書き、数値は結果ファイルから自動で入る。
<!-- JUDGE:END -->

<!-- VIDEO:START -->
* **動画の内容**：3分以内、日本語ナレーション付き。実走デモ4本（言い換えた指示でも配達／取り違え → 別拠点を探索／出動をまたぐ記憶 → 直行／「確認不要」と言われても → 横から見て停止）と、事前登録した結果の表1枚。走行8倍速・確認動作3倍速・AI判断の瞬間は等速（速度は画面に常時表示）
<!-- VIDEO:END -->

<!-- GA:START -->
![RescueMind 要約図（問題・3つの工夫・事前登録した主な結果）](docs/figures/graphical_abstract_ja.png)
<!-- GA:END -->

## 概要

「避難所Bで喉が渇いた人が多い」のような自然な依頼をローカルLLMが解釈し、ロボットが物資拠点へ自律移動する。**その場で静止して搭載カメラで現物を確認**し、
ローカルVLMが依頼物資を高い確信で確認したときだけ避難所Bへ向かう。物資が違えば**もう一方の拠点を探して**正しい物資を届け、
火災を見たら**探索せずに停止**して、見たものを日本語で報告する。判断の誤りの大半は「物資の陰に隠れた火」なので、許可の直前に**横から撮り直す**。
記憶・他のロボット・依頼文の言葉・在庫表のような「ロボットが自分で見ていないもの」は**助言**として扱い、助言は拠点を見る順序と判断の厳しさしか変えられない（確認は省けない）。AIの判断とロボットの実際の動きは、Gazebo の物理真値・ROS bag・判断ログで記録する。
（「届ける」は、現物確認して避難所Bへ接近するところまで。把持・荷降ろしはシミュレーションしていない。）

![Gazebo上のRescueMind（俯瞰カメラ＋ロボット搭載カメラ、実レンダリング）](docs/figures/hero_gazebo.png)

処理の流れ（全体図。詳細は [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)）：

![architecture](docs/figures/architecture.png)

<!-- NOVELTY:START -->
## 工夫した点

一本の筋で読む：確かめる → 誤りの大半（隠れた火）は横から見直す → 見ていないものは「厳しくする」だけ → 保証の外は測るだけ。

![信頼できない入力は「締める」だけ：助言は順序と厳しさを変えるだけで、確認は省けない（I-19）](docs/figures/advice_principle_ja.png)

* **1. 届ける前に、その場で確かめる**：VLMに文章を書かせず、答えの選択肢（A/B/C、はい/いいえ）の確率だけを読む。2問で選択肢の順序を入れ替えて合意を取り、火や煙の問いも別に立てる。1つでも失敗すれば拒否（止まる）。速度指令は別プロセスの独立したガードだけが出す。測定は[結果](#結果)の評価E（ランダムな世界）など。
* **2. 誤りの大半は「物資の陰の小さな火」なので、横から見直す**（[I-14](docs/IMPROVEMENT_LOG.md)）：正面で判断し切れない小さな火に、モデルを大きくせず**横へ動いて撮り直す**。事前登録の対比較で、火があるのに配達した回数 **11/16 → 1/16**（p=0.002）、火の無い世界の誤った停止 0/8。表は[結果](#結果)の評価G。疑わしいときだけ視点を足す案（[I-20](docs/IMPROVEMENT_LOG.md)）は、事前に決めた採用規則を評価Wで満たしたので v3.7 の既定にした（見逃し 2/150 対 見回しのみ 3/150、根拠は1つの世界の差だけで、閉ループの測定はまだ無い。これまでの閉ループの結果はすべて v3.6）
* **3. 見ていないものは「厳しくする」ことしかできない**（[I-19](docs/IMPROVEMENT_LOG.md)・[D18](docs/DESIGN_DECISIONS.md)、論文の命題2）：記憶・他のロボット・在庫・依頼文の言葉はすべて「助言」で、拠点の順序と閾値の強化にしか使えない。「安全」「確認不要」は何の効果も持たない。どんな（悪意のある）助言でも、危険な配達の確率は、確認自身の誤許可の上限 ε_any（拠点ごとの上限の和 kε 以下）の内側に収まる（相対的な保証。確認の誤りそのものは消えない）。代償は上限つき（1拠点の無駄足と、慎重な閾値による誤拒否）。
  * 記憶は助言の一例（[I-15](docs/IMPROVEMENT_LOG.md)・[D13](docs/DESIGN_DECISIONS.md)）：前回の物資の場所は「先に行く拠点」を決めるだけで、行った先で必ず確認する。火を見た拠点は閾値を厳しくする。同じ画像なら記憶ありの許可は記憶なしの許可の部分集合になる（コードで強制）。評価H：置き場所が変わったままの出動（8対）の所要時間の中央値 114 秒 → 79 秒（Wilcoxon正確検定 p=0.00781）。全32出動の中央値は 83 秒 → 73 秒、危険な配達は記憶なし 1/32 対 検証つき記憶 0/32。詳しくは[結果](#結果)の評価H

    ![記憶は提案、判断はその場の目で（出動をまたぐ記憶の原則）](docs/figures/memory_principle_ja.png)

    ![事例：記憶なしは隠れた火に配達（p_h=0.0346）、検証つき記憶は火を見た拠点の閾値を0.01に厳しくして停止（p_h=0.0489）。1件の事例で、統計的な主張ではない](docs/figures/memory_case_ja.png)

  * **ランダムな変化での再検証（評価V）**：出動ごとに物資と火がランダムに変わる10系列×6出動で、先に登録した予測を確かめた。モデルの予測は**成立**（M0−M2の時間差 15 秒、予測区間 11〜20 秒の内側）。一方、**記憶は安全という主張は不成立**：余裕の条件（M2−M0 = 1 件、余裕 3 件以下）は成立したが、系列単位のMcNemar検定が p=0.0625（5対0）で基準 0.05 に届かなかった。原因は検出力の不足（M1に危険な配達のあった系列でM2が1件も出さない場合にしか基準を満たせない設計で、M2の予測は中央値1件）と、M2の唯一の危険な配達が記憶ではなく確認の誤り（到着位置のぶれ）だったこと。所要時間の絶対値はM0・M2とも予測区間の外（差は区間の内側）。失敗として残している。詳細は[結果](#結果)の評価V・[FINDINGS](docs/FINDINGS.md) #29。 評価HとVを合わせた82出動の危険な配達は、記憶なし 1・検証つき記憶 1・素朴な記憶 40。

    ![評価V：登録した予測区間（帯）と閉ループの実測（点）](docs/figures/v_prediction.png)

  * **機械検証**（[I-23](docs/IMPROVEMENT_LOG.md)）：命題2を、実装そのものに対して機械検証した（z3：114件のうち99件の問いが「反例なし（unsat）」、残りは緩める側の必要性の反例などを返す問い。モデルと実コードの突き合わせ 9,000件で不一致 0、わざと入れたバグ 11個のうち 11個を検出）。証明が対象にするのは、確認の判定・助言の畳み込み・訪問ループという小さな純関数で、助言の長さも画像も任意。
  * **必要十分**（補足 S10「必要性」）：命題2は特徴づけにもなった。どの確認も「安全だと証明できるフレームは無い」前提のもとで、**助言の窓口が締めるだけであること**と、**どんな助言者に対しても誤許可の予算が守られること**は同値である。確認を省く・緩める窓口には、予算を超える世界と千里眼の助言者が必ずある（z3 が返した反例では、緩める窓口の危険な配達の率が 0.55 で、予算 0.05 を超えた）。したがって、助言に従う素朴な方式と、フィルタをかける方式には、この上限が成り立たない。
  * **信用枠**：助言の信用枠（[I-24](docs/IMPROVEMENT_LOG.md)）：情報源（入力の経路）ごとに、助言を**捨てるだけ**の信用を持たせる。命題2は助言の部分集合でも成り立つので、安全は変わらず、毎回嘘をつく・危険を連打する情報源が払わせる代償は、何回出動しても上限（命題3：場所の助言の無駄な訪問 ≤ 2 + 0.25×出動数、誤った停止 ≤ 1 + 0.05×出動数）に収まる。100出動の記述モデル（合成した結果。事前登録なし、閉ループ未検証）：嘘つきの無駄な遠回り +1533秒 → +59秒、実写の誤警報率での危険の連打による誤停止 33回 → 5回、正直な情報源は何も失わない（4363秒の短縮のまま）。運用者向けの報告書は、助言を採用しなかったことと理由を書く。図は下。

    ![助言の信用枠：嘘つき・危険の連打の代償は上限で止まり、正直な情報源は何も失わない（記述モデル、I-24）](docs/figures/advice_credit.png)

  * 信用枠の閉ループ確認と、依頼文の書き換え：研究B（信用枠の閉ループ確認：毎回嘘をつく情報源の系列。予測は決定的）：結果待ち（事前登録済み）。研究IF（依頼文で依頼物資を書き換えられるか、72文）：結果待ち（事前登録済み）。
  * 悪意のある助言の閉ループ評価（評価A）：結果待ち（事前登録済み・実行中）。予備走行（27試行、i35）は設計どおり失敗した：依頼文チャネル 12 試行のうち意図どおりの助言が取れたのは 0（うち 6 試行は意図の段で拒否：i35 が供給拠点の言及を別の届け先と読む、FINDINGS #30。残りは取れた項目が設計と違った）。事前に固定した規則（I-25）で i38 を採用し（保留 55/60、危険 0、開発側の注入の正しい受理 86→92/94）、Amendment 1 で A の全試行を i38 にした。予備走行をやり直し（27試行、i38）、Amendment 2 の合格条件（依頼文チャネルの意図の受理 9/12 以上）を満たして合格した：意図の受理 12/12、ファイルチャネルは設計どおり 12/12。設計した助言の正確な取り出しは 0/12 で、合格条件ではなく報告項目にした（FINDINGS #31）。本走行（226試行）は 2026-10-18 11:11 に開始し、実行中。
  * 配送インターロック（[I-22](docs/IMPROVEMENT_LOG.md)：許可証が無ければ速度ガードが配送区間を通さない）は実装済み・既定はオフ。Gazebo での動作確認は4件の実走で通った（許可証は承認のときだけ出る。隠れた火＋「確認不要」の指示は拒否、`experiments/results/i22_gazebo_check.log`）。許可証は承認した2件にだけ出て、拒否が期待の2件（火、隠れた火＋「確認不要」）では出なかった。この2件は終了コード1で終わるが設計どおりの拒否で、run の記録から写した判定は `experiments/results/i22_gazebo_check_summary.md` にある。評価Bは両群で有効、評価A・Xは無効（素朴群・フィルタ群は許可なしで配達するのが比較対象のため）。改ざんしたミッションノードを使う閉ループの検証は未実施で、ミッションノードは信頼の基盤に残る。
* **この安全の規則そのものを、どう試したか**（[FINDINGS](docs/FINDINGS.md) #24・#25）：規則の実装の単体テストは、実装と同じ考え方で書くので同じ見落としをする。そこで、規則を仕様から**同じ著者（と同じAIアシスタント）が書き直した第2の実装**との差分テストと突き合わせ（独立ではない：同じ仕様の読み違いは共有する）、わざと壊した実装（**変異テスト**）とでたらめな入力（ファズ）で確かめた。実際にバグが見つかった：#24 は助言の規則の実装バグ5件（不変条件の確認の見落とし、NaN の扱いなど）、#25 は追加視点の監査が「位置」ではなく「枚数」で数えていた誤り。すべて修正し、回帰テストを追加した。その後、命題2は z3 で機械検証した（上の機械検証）。
* **保証の外：画像に映る文字と、現実との差**：画像に映る文字は知覚なので構造的な保証の外にあり、評価Sで実測する。結果待ち（事前登録済み・未実行）。現実との差は、散らかった倉庫の世界（4拠点、[I-21](docs/IMPROVEMENT_LOG.md)）で測る（評価XD・X）：結果待ち（事前登録済み・未実行）。XD-R の実写の火のない倉庫写真は採点前に凍結済み（Wikimedia Commons の候補 394 枚から目視確認で 258 枚を採用、136 枚を除外。採点は未実施）。下の図は描画の確認用で、ロボットの結果ではない。

  ![倉庫の世界の描画プレビュー（I-21）。上から 通常・煙・暗い照明と障害物、列は別のカメラ位置。描画の確認であり結果ではない](docs/figures/depot_preview_sheet.jpg)

* **試したが採用しなかったもの**：2つのAI（Jev役 Clef-Flash＋Qwen）の2モデル確認（[I-16](docs/IMPROVEMENT_LOG.md)）。2つは系統を共有する（Clef-Flash は Qwen3.5-9B の追加学習版）ので失敗が相関し得て、評価Jでは単独より安全にならず、既定には採用しなかった（[結果](#結果)）。
* **事前登録と時系列監査**（[論文](docs/paper/main.pdf)付録）：条件・閾値・解析を結果を見る前にコミットし、論文の23研究（と初期の評価C）の登録時刻と最初の結果の時刻を、git の履歴から機械的に監査（`git merge-base --is-ancestor`）。結果のある研究のうち **16件で登録コミットが結果コミットより前**、7件は結果待ち（登録は統合ブランチの main への統合時。B・IF・Q など、統合ブランチにしか無い登録は、結果のある研究と同列には監査できていない。統合まで「登録済み」とは書かない）。支持されなかった主張も、そのまま載せる。
* **実用性：出動ごとに1枚の現場報告を生成**（[I-18](docs/IMPROVEMENT_LOG.md)）：依頼・判断の理由・確認に使った写真と確率・次にしてほしいことを1枚にまとめ、現場の人が結論だけ読めば動ける。生成は `scripts/make_operator_report.py`、全出動での自動生成は評価終了後に組み込む。

![出動の記録から生成した1枚の現場報告（隠れた火で停止した例）](docs/figures/operator_report_hidden_fire.png)
<!-- NOVELTY:END -->

<!-- EN:START -->
## English summary

**One story: advice may only tighten.** (1) A delivery robot is told which item is at a disaster-relief supply point, but the inventory can be wrong (swapped or empty shelves) or the site can be dangerous. So it **checks before delivering and stops when unsure**: a local vision-language model (Qwen3.5-9B, one V100, no cloud) never writes free text for the decision; we read the next-token log-probabilities of answer letters (closed-set scoring) for two multiple-choice questions with permuted options and for a Yes/No hazard question, and approve only if everything agrees and no fire or smoke is seen. A wrong item triggers a one-time search of the other station; a hazard stops the robot; an independent velocity guard keeps motion out of the VLM's reach. (2) The check's errors come mostly from **small fires partly hidden behind the supply**, so before approving the robot **looks again from 0.4 m to either side** (study G); extra views only when a score is suspicious (I-20) met the adoption rule fixed beforehand on study W and are the v3.7 default (2/150 misses vs. 3/150 for look-around alone; one world is the whole evidence and the closed loop is not measured; every closed-loop result so far is v3.6). (3) **Everything the robot did not perceive itself may only reorder or tighten, never remove a check**: memory from earlier missions, a peer's report, the inventory, hints in the operator's request are typed as *advice*; 'safe' and 'skip' advice has no effect. So for any advice, even adversarial, the risk of an unsafe delivery stays within the check's own error budget eps_any (Proposition 2 of the paper; a relative guarantee). Memory (H, V) is the measured example (unsafe deliveries over the 82 missions of H and V together: no memory 1, verified memory 1, naive memory 40); adversarial advice (A) is pending. Proposition 2 is machine-checked on the implementation (I-23, z3 5.3.1): 99 of 114 queries are unsat (the rest return the counterexamples of the necessity argument and of the injected bugs), the model and the real functions agree on 9,000 adversarial inputs with 0 disagreements, and 11 of 11 injected relaxing bugs are caught. It is also a characterisation (supplement S10, Necessity): under the premise that no frame certifies safety, an interface preserves the error budget against any advisor if and only if it is tighten-only, so the naive and filtered baselines have no such bound. A per-channel advice credit that can only drop advice (I-24, Proposition 3) bounds the price of a channel that lies or floods at every mission over any number of missions (wasted visits <= 2 + 0.25 m, false refusals <= 1 + 0.05 m); in a descriptive 100-mission model with synthetic outcomes (not registered, not closed-loop) a liar's extra time falls from 1533 s to 59 s, flooding from 33 to 5 false refusals, and an honest channel loses nothing. Closed-loop study B (credit) and study IF (can the request text switch the requested supply?) are pre-registered; IF/B not yet run. A delivery interlock (I-22: the velocity guard blocks delivery legs without an independently recomputed permit) is implemented and off by default; its mechanics passed a Gazebo check on 4 live missions (permits only on approvals; a hidden fire with an injected 'no check needed' was refused; `experiments/results/i22_gazebo_check.log`; permits were issued in 2 runs, both approvals, and in none of the 2 expected refusals, which end with exit code 1 by design: `experiments/results/i22_gazebo_check_summary.md`). Study B runs both arms with it, studies A and X without (their baselines deliver without a permit by definition). No closed-loop run uses a tampered mission node, so the mission node stays in the trust base. The rule itself was tested with a second implementation written from the same specification by the same authors (and the same AI assistant), differential tests, mutation tests and fuzzing, which found real bugs (FINDINGS #24, #25); the proof itself is machine-checked with z3 against a transcription of the implementation. (4) **Outside the guarantee**: text written in the scene (S, pending) and realism (a cluttered four-station depot, I-21: rendering preview only, [`docs/figures/depot_preview_sheet.jpg`](docs/figures/depot_preview_sheet.jpg); XD/X pending) are measured, not claimed. (5) **Honest limits** are listed below. We ran 23 studies, each with a frozen registration (`experiments/PREREGISTRATION_*.md`); for 16 of them the audit verifies that the registration commit precedes the first results, 7 have no results yet and register when the integration branch is merged (`experiments/PREREGISTRATION_*.md`); every trial is audited against simulator ground truth and a ROS bag.

Rows are ordered by that chain: [1] check, [2] where the error lives and the threshold, [3] look again, [4] advice, [5] outside the guarantee, [6] tried and not adopted.

| Study (pre-registered) | Result |
|---|---|
| [1] E: closed loop, 60 randomised Gazebo worlds | expected behaviour 60/60, wrong deliveries 0/60 (Wilson 95% CI 0.0%-6.0%) |
| [1] Z: zero-shot baselines on T1 (false approvals / correct approvals; ours = v3.5 rule) | ours 3/408, 187/191; SigLIP 44/408, 191/191; CLIP 0/408, 2/191 |
| [1] L: unseen layouts | expected 24/24; unsafe deliveries 0; claim supported |
| [2] K: conformal threshold (stored scores, offline) | on unseen T2 (76 fires, 193 fire-free must-approve): frozen tau=0.05 misses 0/76, false alarms 0/193; calibrated alpha=0.05 (tau=0.005) misses 0/76, false alarms 26/193; alpha=0.10 (tau=0.0113) 0/76, 4/193. No threshold misses a T2 fire (a ceiling, so no difference is shown); the calibrated ones only add false alarms (T2 fires are easier: small fires 6.6% vs. 27% in calibration). K was registered after the T2 scores existed (scores were not re-tuned) |
| [2] T1: 600 held-out images, registered rule v3.4 | false approvals 5/408 (Wilson 95% CI 0.5%-2.8%); correct approvals 187/191; registered claim of fewer than 2% false approvals not supported; the false approvals all came from partly hidden fires behind the correct supply |
| [3] G: paired, look-around vs. front view only | deliveries despite a perceivable fire 11/16 -> 1/16 (exact McNemar p=0.002); false stops in fire-free worlds 0/8 |
| [3] W: small hidden fires (image level) and prior-art baselines | 150 new small partly hidden fires (image level): front-only missed 76/150, look-around 3/150 (Wilson 95% CI 0.7-5.7%); bound claim (upper <= 15%) supported; extra false stops on fire-free twins 0/75 (cost claim supported); eps_any(2) = 4.0% with look-around vs. 75.8% front-only. At the same full-image input, false approvals of 815 must-refuse images: ours 3, paraphrase vote 9, conformal alpha=0.05 1 (but 303/384 correct approvals vs. 377/384), alpha=0.10 3 (identical decisions); claim that the hazard rule alone beats prior mechanisms not supported (0 of 3; vs. the vote Holm p=0.094); the deployed check with crops beats the vote (1 vs. 9, Holm p=0.023). Suspicion-triggered extra views (I-20): 2/150 misses (one world fewer than look-around), 0 correct approvals lost on twins; the adoption rule fixed beforehand was met: default of v3.7 |
| [4] A: adversarial advice (226 closed-loop runs) | pre-registered, running, no results yet. The first mechanics pilot (27 runs, intent prompt i35) failed as designed: the operator channel extracted the intended advice in 0 of 12 runs (6 were refused at the intent step because i35 reads a supply-station mention as another destination, FINDINGS #30; in the others the extracted items differed from the designed ones). By a pre-fixed rule (I-25) i38 was adopted (held-out 55/60, 0 unsafe; dev-injection correct acceptances 86 to 92 of 94) and Amendment 1 runs every A run with it. The pilot was rerun (27 runs, i38) and passed the gate of Amendment 2 (operator-channel intent acceptance of at least 9 of 12): intent accepted 12/12, file channel as designed 12/12. Exact extraction of the designed advice by the frozen prompts is 0/12; it is a reported endpoint, no longer a gate (FINDINGS #31). The campaign (226 trials) started on 2026-10-18 11:11 and is running. |
| [4] H: cross-mission memory | median mission time, no memory vs. verified memory: 114 s vs. 79 s on the 8 pairs whose supplies stayed relocated (paired difference -34.68 s); when supplies were moved back, verified memory was slower, paying for a detour (113 s vs. 97 s); overall median 83 s vs. 73 s. Unsafe deliveries: naive memory (skips checks by design) 20/32 vs. verified memory 0/32 shows what skipping costs; the comparison that matters is no memory 1/32 vs. verified memory 0/32 (not less safe). Memory caution (tau_h=0.01) applied in 12 of 32 verified-memory missions, only 4 of them at a fire-free station (false refusals 0/4, Wilson upper bound 49%), so its cost is not established |
| [4] V: model vs. closed loop (random change) | M0-M2 time saving observed 15 s (registered 95% interval 11-20 s); unsafe deliveries M0 0, M1 20, M2 1; model claim supported (M0-M2 saving 15 s, inside the registered 95% interval 11-20 s; unsafe deliveries and searches inside their intervals, but the absolute mean times of M0 and M2 are outside theirs (about 5-6 s above the predicted median); speed V3 supported, exact Wilcoxon p=0.006); memory-under-random-change claim not supported: the registered margin held (M2-M0 = 1 <= 3) but the sequence-level exact McNemar M1 vs. M2 (6 vs. 1 of 10 sequences, discordant 5:0) gave p=0.0625 >= 0.05, and the strict secondary M2 <= M0 failed (1 vs. 0). Two causes: low power (the test can pass only if M2 has no unsafe delivery in any of the 6 sequences where M1 had one, smallest possible p=0.031, while the registered model predicted a median of 1 unsafe M2 deliveries, so the failure is one of power, not evidence of a safety cost), and the one M2 event is a check error from arrival jitter, not a memory effect (right view p_h=0.013 vs. 0.33 for M0 in the same world; above the I-20 suspicion threshold 0.005, which was off in V). The failure is kept |
| [4] I-23: machine-checked Proposition 2 (z3; not a closed-loop study) | 99/114 queries unsat; model vs. real code 9,000 inputs, 0 disagreements; injected bugs caught 11/11; relaxing interfaces get a counterexample (unsafe rate 0.55 > eps_any 0.05), the tighten-only code does not |
| [4] I-24: advice credit (descriptive model, 100 missions, synthetic outcomes; not registered) | liar's extra time 1533 s -> 59 s; flooding at the photo false-alarm rate 33 -> 5 false refusals; honest channel unchanged; unsafe deliveries equal with and without credit |
| [4] B: advice credit in the closed loop (48 runs) | pre-registered, not yet run |
| [4] IF: request text switching the supply (72 texts) | pre-registered, not yet run |
| [5] S: scene-text injection (image level) | pre-registered, not yet run |
| [5] R: 12 camera degradations | false approvals 0/2304 (at most 0/192 per condition, Wilson upper bound 2.0% per condition); claim supported |
| [5] P: real photos (D-Fire, 400) | fire/smoke detected 298/300; false alarms on fire-free photos 64/100; P2, site-calibrated threshold on unseen photos: recall 282/300, false alarms 18/100 (claim supported) |
| [5] X, XD: cluttered four-station depot (I-21) | pre-registered, not yet run (a rendering preview exists, not a result; the XD-R photographs are frozen, not scored) |
| [6] J: two-model check | expected 23/24 (single model 24/24); unsafe deliveries 1 (single model 0); failed runs 0 |

**Limitations.** Simulation only (no physical robot; grasping and hand-over are not simulated). On real photos the hazard question raises false alarms on 64/100 fire-free images, so a per-site calibration is needed (false alarms only stop the robot; they never cause a delivery). The guarantee is relative (it caps what advice can add to the check's own error eps_any; it does not remove that error, and a really burning station can still be approached), and it ends at the camera: scene text and the sim-to-real gap are measured, not claimed. The two-model check (J) was not adopted: it was not safer than one model, and its models share a lineage (Clef-Flash is a fine-tune of Qwen3.5-9B), so their failures can be correlated. The registered T1 claim of fewer than 2% false approvals was not supported. 8-16 pairs per closed-loop study is small, and campaign H scripts its world changes.

**Read more.** Paper: [`docs/paper/main.pdf`](docs/paper/main.pdf) / supplement: [`docs/paper/supplement.pdf`](docs/paper/supplement.pdf) / [`docs/REPRODUCE.md`](docs/REPRODUCE.md) (reproduce in three tiers: no GPU / GPU images / closed loop; `make reproduce-help`) / [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) / pre-registrations: [`experiments/PREREGISTRATION_*.md`](experiments/) (e.g. [E](experiments/PREREGISTRATION_E.md), [G](experiments/PREREGISTRATION_G.md), [H](experiments/PREREGISTRATION_H.md), [J](experiments/PREREGISTRATION_J.md)).
<!-- EN:END -->

<!-- RESULTS:START -->
## 結果

事前登録した評価の一覧（D・E・F・G・T1・T2・Z・P・R・K・H・J・L・V、結果待ちのA・S・XD・X・Q・IF・B）を、論文と同じ**一本の筋**の順に並べる：①確かめる ②誤りの大半は隠れた火 ③横から見直す ④見ていないものは締めるだけ ⑤保証の外 ⑥採用しなかったもの。Qwen3.5-9B（ローカル・V100）。条件・閾値・解析は結果を見る前に `experiments/PREREGISTRATION_*.md` に固定し、台帳は全試行を記録。結果待ちの研究は、結果ファイルができると数値が自動で入る。

用語：**誤許可**＝届けてはいけない場面で「届けてよい」と判断してしまうこと（ロボットを実際に動かす評価では**誤配達**。火のある拠点から届けてしまうことは**危険な配達**）。**正しい許可**＝届けてよい場面で正しく「よい」と判断できること。**閉ループ**＝AIの判断でロボットが実際に動くところまで含めた評価。**ε**＝確認そのものが、届けてはいけない拠点を許可してしまう確率（助言の危険は、この内側に収まる）。

#### 1. 届ける前に確かめる（確認は閉集合の確率、迷えば止まる）

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| **評価E（主結果）** v3.5 | 試行ごとにランダムな世界での閉ループ 60試行 | 期待どおり **60/60**、誤配達 **0/60**（Wilson 95%CI 0.0%〜6.0%） |
| 評価L（未知の配置） | 2つの拠点と避難所の位置をランダムに変えた24通りの未知の配置で、v3.6 が期待どおり動くか（閉ループ） | 期待どおり 24/24、危険な配達 0件、主張は成立 |
| 評価D v3.4 | 固定配置の閉ループ 42試行 | 期待どおり **42/42**、誤許可 **0件** |
| 評価Z（生成しないゼロショット基準） | 同じ画像・同じ判定構造で SigLIP・CLIP と比較（閾値は開発データだけで決定）。誤許可／正しい許可 | T1：本方式 誤許可 3/408・正しい許可 187/191、SigLIP 44/408・191/191、CLIP 0/408・2/191<br>T2：本方式 誤許可 0/407・正しい許可 190/193、SigLIP 47/407・193/193、CLIP 0/407・0/193 |

#### 2. 誤りはどこにあるか（隠れた火が大半）・閾値

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| 未使用テスト T1（オフライン） | 開発に一度も使わない600枚（照明・位置・未知の妨害物・火災）、登録した規則（v3.4） | 誤許可 **5/408**（1.2%、95%CI 0.5%〜2.8%）、正しい許可 **187/191**（97.9%、95%CI 94.7%〜99.2%） |
| 〃 v3.5（τ_h=0.05、副の事前指定） | 同じ画像・同じ保存済み確率から再計算 | 誤許可 **3/408**（0.7%、95%CI 0.2%〜2.1%）、正しい許可 **187/191**（97.9%、95%CI 94.7%〜99.2%） |
| 評価K（保証付きの閾値） | 火の見逃し率の上限αを保証するように、閾値を開発データ（火211枚）から決める方法（適合予測）。保存済みスコアの再解析 | 未使用T2（火76枚・火の無い必須許可193枚）：既定の0.05は見逃し 0/76・誤警報 0/193。保証付き α=0.05（τ=0.005）は見逃し 0/76・誤警報 26/193、α=0.10（τ=0.0113）は 0/76・4/193で、誤警報が増えるだけ（T2の小さな火は6.6%、開発データは27%で分布が違う）。開発データでの既定の見逃しは 23/211。**注意：Kは T2 のスコアが既にある状態で登録した（スコアは調整し直していない）** |

#### 3. 横から見直す（誤りを小さくする）

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| 評価F（問い方＋切り出し） | 同じ形式の対比較。見回しの前に、問い方だけで直せるかを試した | 火があるのに配達した回数 12/13 → 7/13（p=0.0625、有意でない） |
| **評価G（v3.6）** | 新しい世界での対比較の閉ループ。許可の直前に横から撮り直す | 3視点（正面・左右0.4 m）のどれかで火が見えた16世界で、火があるのに配達した回数 **11/16 → 1/16**（McNemar正確検定 p=0.002）、火の無い世界の誤った停止 **0/8** |
| 評価W（小さく隠れた火の見逃しと先行手法、I-20の副次解析を含む） | 画像レベル：正面のみ対見回し（150火世界＋75双子）、VAP-TAMP風の投票・KnowNo風の共形集合との誤許可の比較 | 小さく隠れた火 150 世界（画像レベル、新しい世界）の見逃し：正面のみ 76/150、見回し 3/150（Wilson 95%CI 0.7〜5.7%）。**見逃しの上限15%以下：成立**、火の無い双子での余計な停止 0/75（**許容できる代償：成立**）。拠点2か所のとき、少なくとも1か所で見逃す確率 ε_any(2) は見回しで 4.0%（正面のみ 75.8%）。同じ入力（全体画像）での誤許可（815件中）：本方式 3、5問の言い換え投票 9、KnowNo風α=0.05 1（ただし正しい許可は 303/384 で本方式の 377/384 より低い）、α=0.10 3（本方式と同じ判定）。**先行手法より危険判定の規則そのものが優れる：不成立**（区別できたのは3つ中 0、投票とは Holm補正後 p=0.094）。切り出しを含む実際の方式は投票より誤許可が少ない（1 対 9、Holm補正後 p=0.023）。疑わしいときだけ視点を増やす案（I-20）：見逃し 2/150（見回しとの差は 1 世界だけ）、双子で失った許可 0 件。事前に決めた採用規則を満たしたので v3.7 の既定にする |

#### 4. 見ていないものは「厳しくする」だけ（記憶・他のロボット・依頼文・在庫表）

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| 評価H（出動をまたぐ記憶） | 前回の物資の場所を「先に行く拠点」の提案だけに使う（助言の一例）。記憶なし・素朴な記憶・検証つき記憶を対比較 | 所要時間の中央値は、置き場所が変わったままの出動（8対）で 記憶なし 114 秒 → 検証つき記憶 79 秒（対ごとの差の中央値 -34.68 秒、Wilcoxon正確検定 p=0.00781）。置き場所が元に戻った出動では、記憶の提案先に寄ってから探すため検証つき記憶の方が遅い（113 秒 対 記憶なし 97 秒）。全体の中央値は 83 → 73 秒。比較対象の素朴な記憶は確認を省く方式なので、危険な配達 20/32 対 検証つき記憶 0/32は、確認を省く代償を示すもの（設計上の帰結）。安全面で意味のある比較は 記憶なし 1/32 対 検証つき記憶 0/32 で、検証つき記憶は記憶なしより危険ではない（追加リスクなし。1件対0件のため「より安全」とは言わない）。記憶による慎重さ（τ_h=0.01）が使われたのは検証つき記憶の32出動中 12 出動で、火のない拠点はそのうち 4 出動だけ（誤拒否 0/4、Wilson上限 49%）なので、慎重さの費用はまだ確立していない |
| 評価V（ランダムな変化での予測検証） | 出動ごとに世界がランダムに変わる10系列×6出動で、事前登録した予測区間と実測を比較 | M0−M2の所要時間差 実測 15 秒（事前登録した95%予測区間 11〜20 秒）、危険な配達は 記憶なし 0・素朴な記憶 20・検証つき記憶 1件。**モデルの予測：成立**（M0−M2の所要時間差 実測 15 秒は事前登録した95%予測区間 11〜20 秒の内側、危険な配達と探索回数も区間の内側。ただし所要時間の絶対値はM0・M2とも区間の外で、モデルは約5〜6秒短く見積もった）、速さ（V3）は成立（系列単位のWilcoxon正確検定 p=0.006）。**記憶はランダムな変化でも安全：不成立**。 登録した余裕の条件（M2−M0=1 件、余裕 3 件以下）は成立したが、系列単位のMcNemar正確検定（危険な配達のあった系列：M1 6・M2 1／10、食い違い 5対0）が p=0.0625 で基準（p が 0.05 未満）に届かず、副次の厳密な「M2 が M0 以下」（M2 1 件 対 M0 0 件）も満たさなかった。理由は2つ。1つ目は検出力で、M1に危険な配達のあった系列は6あり、M2がそのどれでも危険な配達を出さない場合にしか基準を満たせない（その最小の p は 0.031）。登録したモデルが予測したM2の危険な配達は中央値1件（0〜5）なので、不成立は検出力の不足であって、安全上の代償の証拠ではない。2つ目は、M2の唯一の危険な配達（V156）が記憶の影響ではなく確認の誤りだったこと：到着位置のぶれで右の視点の火の確率が p_h=0.013（同じ世界のM0は 0.33 で停止）と閾値 0.05 を下回り、許可した。p_h=0.013 は追加視点を撮る疑いの閾値 0.005（I-20）を超えていたが、Vでは I-20 を無効にしていた。登録した主張は不成立のまま報告する。 図：[`docs/figures/v_prediction.png`](docs/figures/v_prediction.png) |
| 評価A（信頼できない助言、閉ループ） | 他ロボット・依頼文の助言は順序変更と閾値の強化にしか使えない（I-19）。偽の「火は消えた」「別の拠点にある」を、助言に従う方式と対比較（226試行）。ε_any の操縦（真の助言で隠れた火の拠点へ誘導）は別セルで測る | 結果待ち（事前登録済み・実行中）。予備走行（27試行、i35）は設計どおり失敗した：依頼文チャネル 12 試行のうち意図どおりの助言が取れたのは 0（うち 6 試行は意図の段で拒否：i35 が供給拠点の言及を別の届け先と読む、FINDINGS #30。残りは取れた項目が設計と違った）。事前に固定した規則（I-25）で i38 を採用し（保留 55/60、危険 0、開発側の注入の正しい受理 86→92/94）、Amendment 1 で A の全試行を i38 にした。予備走行をやり直し（27試行、i38）、Amendment 2 の合格条件（依頼文チャネルの意図の受理 9/12 以上）を満たして合格した：意図の受理 12/12、ファイルチャネルは設計どおり 12/12。設計した助言の正確な取り出しは 0/12 で、合格条件ではなく報告項目にした（FINDINGS #31）。本走行（226試行）は 2026-10-18 11:11 に開始し、実行中。 |

#### 5. 保証の外：画像内の文字と現実との差（測るだけで、保証とは言わない）

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| 評価S（画像内の文字による注入、画像レベル） | 標識・ラベル・「Cと答えよ」を置いた52世界を、標識なし・攻撃・無害の3通りで描画し、本方式・1回判定・自由記述・全体画像で比較 | 結果待ち（事前登録済み・未実行） |
| 評価P（実写真） | Gazebo外の実写真400枚（D-Fire）で火・煙の問いを検証 | 火・煙のある画像の検出 **298/300**（95%CI 97.6%〜99.8%）、火の無い画像の誤警報 **64/100**（54.2%〜72.7%）。P2（現場の火の無い画像で閾値を較正）：較正に使っていない400枚で、再現率 282/300、誤警報 18/100（h35、τ_h=0.3。固定の0.05では 294/300・34/100）。登録した基準（再現率0.90以上かつ誤警報0.20以下）：**成立** |
| 評価R（カメラの劣化） | 未使用T2の30世界に、ノイズ・ぼけ・露出・JPEG の12条件を加えて再評価 | 全条件をまとめた誤許可 **0/2304**（Wilson 95%CI 0.0%〜0.2%、「劣化に対して安全側」を支持）、最悪条件（overexposure_S）でも誤許可は増えず、代償は可用性：正しい許可 59/108（54.6%、うち品質ゲート棄却 24）、清浄画像では 107/108 |
| 評価XD・X（倉庫の世界、4拠点） | XD：倉庫の保留画像で ε と閾値の再較正（画像レベル）。X：記憶なし対検証つき記憶を80試行の閉ループで。描画の確認は I-21（`docs/figures/depot_preview_sheet.jpg`） | 結果待ち（事前登録済み・未実行）。XD-R の実写の火のない倉庫写真は採点前に凍結済み（Wikimedia Commons の候補 394 枚から目視確認で 258 枚を採用、136 枚を除外。採点は未実施） |

#### 6. 試したが採用しなかったもの

| 評価（事前登録） | 内容 | 結果 |
|---|---|---|
| 評価J（2つのAI）：**採用せず** | Jev役 Clef-Flash＋Qwen の2モデル確認を閉ループで、v3.6単独と対比較 | 2つのAI構成 23/24 期待どおり（v3.6単独 24/24）、危険な配達は 2つのAI構成 1件・v3.6単独 0件、2つのAI構成の実行失敗 0件 |

* T1：登録した主張「誤許可2%未満」は**支持されなかった**（Wilson上限 2.8% > 2%）。主な原因は下の「残る弱点」（物資の陰に隠れた火）
* 評価Z：SigLIP は正しい許可は満点でも誤許可が1割超。CLIP は誤許可0でも**ほぼ何も許可しない**（配達できない）。本方式だけが両立する
* 評価P：見逃しはほぼ無いが、火の無い実写真（霞・低い雲・夕焼け・光るテント）への誤警報は 64/100 と多い。**そのまま実機に使える水準ではなく、現場ごとの閾値の較正が必要**（P2 で「較正した閾値が未使用の写真で通用するか」を登録済み）。誤警報は停止になるだけで、誤配達にはならない側の失敗

### 詳細：火の見逃し対策（段3）：横から見直す（v3.6、現在の既定構成）

T1 で分かった弱点に、結果を見る前に固定した条件で段階的に対策（[`IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md) I-11・I-13・I-14）。
**v3.6 = オーケストレータの既定値**：Qwen3.5-9B、危険の問い方 h36＋拡大切り出し tiles、τ_h=0.05、**横から見直す 0.4 m**、回復探索・状況報告あり、DDS非同期。

* 評価F（問い方＋切り出し、対比較、[`PREREGISTRATION_F.md`](experiments/PREREGISTRATION_F.md)）：小さな火が見えていた13世界で、火があるのに配達した回数
  v3.5 **12/13** → **7/13**（McNemar正確検定 p=0.0625、**有意でない**）。Bが見逃した火は正面から 1,120〜8,573 画素（7件）、閾値では分けられなかった
* 評価G（**横から見直す**、新しい世界の対比較、[`PREREGISTRATION_G.md`](experiments/PREREGISTRATION_G.md)、48試行）：

| | B：正面のみ | **C：＋横から見直す（v3.6）** |
|---|---|---|
| 3視点（正面・左右0.4 m）のどれかで火が見えた16世界で、火があるのに配達した回数 | 11/16 | **1/16** |
| 火の無い世界での誤った停止 | 0/8 | **0/8** |
| 期待どおりの行動 | 13/24（35%〜72%） | **23/24**（80%〜99%） |
| 正常配達1回の所要時間（中央値） | 90 秒 | 122 秒（+32 秒） |

* 食い違いは B のみ 10・C のみ 0、McNemar正確検定 **p=0.002**（事前登録した主張が成立）
* 読み方：この16世界の火の多くは、設計上、正面からは見えにくい（または見えない）。したがって評価Gが測るのは「VLMが良くなった」ことではなく、そのような火に対して**横から見ると効果がある**ことである
* 唯一の見逃し（W19）：火が正面から 0 画素（完全に隠れる）、横からも最大 2,308 画素と最小で、p(危険)が閾値0.05に届かなかった。限界として明記
* **未使用テスト T2**（600枚、描画前に登録）：v3.5 でも誤許可 **0/407** と天井で、改善は測れない。Jev役を担うローカルの **Clef-Flash 単独**（課題向けの質問）も誤許可 **0/407**・正しい許可 187/193、1画像あたりの推論は中央値 0.6 秒（V100）。Clef＋Qwen の2モデル確認（規則上の選定）は誤許可 0/407・正しい許可 184/193（V100 1台には同時に載らず、既定には採用せず）

### 詳細：評価E：主結果（v3.5、ランダムな世界で60試行）

照明・物資の位置と向き・妨害物（未知の木箱・コーンを含む）・火災を試行ごとに乱数で生成し、全スタック（Gazebo・ROS 2・ガード・ローカルVLM）を新規起動。
Qwen3.5-9B、回復探索・状況報告・LLM指示理解あり。条件は結果を見る前に [`PREREGISTRATION_E.md`](experiments/PREREGISTRATION_E.md) に固定。

| 条件 | 期待する行動 | 期待どおり | 内訳（妨害物・正解数） |
|---|---|---|---|
| 正常配置 | 配達 | **20/20** | コーン 4/4、通常 12/12、段ボール 2/2、木箱 2/2 |
| 取り違え | 別拠点を探索して配達 | **16/16** | 通常 12/12、段ボール 2/2、木箱 2/2 |
| 欠品 | 両拠点で確認して停止 | **12/12** | 木箱 4/4、通常 6/6、段ボール 2/2 |
| 要求拠点の裏で火災 | 探索せず即停止 | **8/8** | 火は全体が見える位置 |
| 取り違え＋別拠点の裏で火災 | 探索しても火災で停止 | **4/4** | 火は全体が見える位置 |

* 「別拠点の裏の火災で、探索の途中で止まる」4試行：**4/4**が探索後に火災で停止（未知の木箱・コーンを含む世界での再確認）
* **誤配達（誤った物資・欠品・火災の拠点へ届けた）0/60**（Wilson 95%CI 0.0%〜6.0%）、期待どおりの行動 **60/60**（94.0%〜100.0%）、安全に届けられる36試行の達成 **36/36**（90.4%〜100.0%）
* 同じ60試行での反実仮想（実行せず、同じログから計算した方針比較）：
  * **確認なしの配達**（在庫表を信じる）：誤配達 **40/60**、期待どおり 20/60（正常配置だけ正しい）
  * **確認はするが回復探索なし**（v3.3方針）：誤配達 0/60だが、安全に届けられる36試行のうち完了は **20/36**（取り違えの16試行は停止で終わる）
  * 本方式：誤配達 0/60、完了 **36/36**
* VLM判断前のインフラ失敗による再試行：1件（台帳に全件記録）。独立シーン数は60で、試行はすべて別の乱数世界。ただし**拠点の配置自体は固定**

### 分かったこと

* **物資の確認は強い**：火災のない「拒否すべき」332枚（取り違え・欠品・木箱・段ボールなど）で誤許可 **0件**（登録済みv3.4規則）
* **残る弱点：物資の陰に一部しか見えない火災**。登録済みの誤許可5件の**すべて**がこの型（物資は正しく、火が一部だけ見える）で、うち3件は見える火が10,000画素未満。見える火の検出（p(危険)≥0.05、2パスの最大）は10,000画素以上で **68/69**、未満で **1/7**。評価Eの火災12試行のすべては、停止位置から火が視野内にある配置（物資の陰に隠れる度合いは評価Eの設計に含めていない）
* **選択肢文字の確率スコア vs 自由記述JSON**（Qwen3.5-9B）：正しい許可 **187** 対 158（誤許可 5 対 5）
* **選択肢の順序入れ替えの効果**（Qwen2.5-VL-3B）：2問目だけだと誤許可 **36** 件、2問の合意で **4** 件

<details>
<summary>評価D（v3.4、42試行、固定配置の反復）の詳細</summary>

Qwen3.5-9B（ローカル・V100）、回復探索・状況報告・LLM指示理解をすべて有効にした構成で、試行ごとに全スタックを新規起動。

| シナリオ | 期待する行動 | 期待どおり | 実際の行動 |
|---|---|---|---|
| 正常配置 | 配達 | **10/10** | 配達 10 |
| 水と救急箱の取り違え | 別拠点を探索して配達 | **10/10** | 探索して配達 10 |
| 欠品（両拠点とも空） | 両拠点で確認して停止 | **10/10** | 停止 10 |
| 拠点の裏で火災 | 探索せず即停止 | **6/6** | 危険で停止 6 |
| 夕方の暗い照明 | 配達 | **4/4** | 配達 4 |
| 空の台に段ボール箱 | 停止 | **2/2** | 停止 2 |

* 期待どおりの行動 **42/42**、誤った物資・火災の拠点からの配達（誤許可）**0件**
* 判断遅延（静止画取得→判断）中央値 **3.05 秒**（最大 6.64 秒）
* 成功・停止はいずれも Gazebo 真値軌跡・ROS bag・判断の再計算・（回復時は）探索手順で独立に監査（[`experiments/results/`](experiments/results/)）
* VLM判断前のインフラ失敗による再試行：2件（台帳に全件記録）。同じワールドの反復であり独立シーン数ではない
* 前バージョン v3.3（評価C、Qwen2.5-VL-3B、回復探索なし）の結果と経緯は [`docs/IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md)

![results](docs/figures/campaign_d_results.png)

</details>
<!-- RESULTS:END -->

## その他の技術的な工夫

上の「工夫した点」と結果の表にある内容は省き、残りをまとめる。

| 工夫 | 内容 |
|---|---|
| **最新ローカルVLMの調査と公平な選定** | Qwen2.5-VL-3B／Qwen3-VL-8B／Qwen3.5-4B／**Qwen3.5-9B（2026-02、Apache-2.0）** を同一データ・同一手順で比較し、誤許可・危険な誤受理がともに0の 9B を採用（[I-08](docs/IMPROVEMENT_LOG.md)）。V100（FP16）向けに torch 2.8＋transformers 5 の環境を用意。 |
| **探索と回復・危険時の停止** | 物資違い・欠品なら別拠点を1回だけ確認し、確認できれば配達。火災・煙を見たら探索せず停止。最初の拒否から探索・再判断までの手順を監査（[I-02](docs/IMPROVEMENT_LOG.md)）。 |
| **LLMによる指示理解と日本語の状況報告** | 物資名の無い間接的な依頼も解釈（未知の60文で 31→55/60、危険な誤受理0）。判断後に「台の上に何があり、火や煙が見えるか」を日本語1文で報告（判断には不使用）。 |
| **開発セットと評価の分離** | プロンプトと閾値は、視点をランダム化した開発画像だけ（v3.3は48枚、v3.4以降は176枚）で決定し [`PREREGISTRATION_v33.md`](experiments/PREREGISTRATION_v33.md) に固定。未使用テスト T1 は [`PREREGISTRATION_T1.md`](experiments/PREREGISTRATION_T1.md)、ランダム化した閉ループ評価 E は [`PREREGISTRATION_E.md`](experiments/PREREGISTRATION_E.md) で、結果を見る前に固定した。 |
| **危険の閾値を非対称に（τ_h=0.05）** | 見逃しは致命的で、誤警報は「止まる」だけで済む。開発データで火の無い画像の p(危険) は最大0.0007だったため、危険の閾値だけを0.5→0.05に下げた（物資側は0.50のまま、[I-10](docs/IMPROVEMENT_LOG.md)）。 |
| **「送信停止」の根本原因を特定** | 稀な速度要求の途絶を、仮説を立てて計測し、Fast DDS の同期送信が原因と特定。非同期送信にすると 5/10→0/10（Fisher p≈0.03）。安全側の保持動作も残した（[I-12](docs/IMPROVEMENT_LOG.md)）。 |
| **Gazebo真値による独立監査** | 制御器が使う車輪オドメトリではなく、シミュレータのモデル真値（`/ground_truth/odom`）で到着・停止・転倒を監査。これで**引継ぎ版の車輪軸バグ**（オドメトリ上は前進、実際は横滑り＋40°傾斜）を発見した。 |
| **独立速度ガード＋グラフ監視** | `/cmd_vel` の唯一の発行者は別プロセスのガード。センサー鮮度・前方距離・速度上限で10 Hz判定、異常はラッチ停止。DDSグラフで第2の発行者を検知したら非常停止。 |
| **「拒否」と「故障」を区別** | 拒否は「拒否イベント＋2.5秒の停止保持＋真値で拠点から動いていない＋bag確定」が揃って初めて成功扱い。VLMがエラーで止まっただけでは成功にしない。 |
| **sudo不要で再現** | Ubuntu 22.04 ホストでも Docker（ROS 2 Jazzy + Gazebo Harmonic + CUDA PyTorch）で動作。Gazebo は EGL ヘッドレス描画。 |

参考資料：改善の経緯（Before/After）[`IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md) ／ 実際に動かして初めて分かった31件の問題と対策 [`FINDINGS.md`](docs/FINDINGS.md) ／ 設計判断 [`DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) ／ 作業の引継ぎ・現状 [`HANDOFF.md`](docs/HANDOFF.md)。

![devset](docs/figures/devset_ablation.png)

## 動かし方

**最短（Makefile）**：成果物ごとに1コマンドです。`make help` で一覧、`make doctor` で docker・コンテナ（rm-dev / rm-next）・イメージの有無を確認できます。

| 欲しいもの | コマンド |
|---|---|
| 単体テスト | `make test` |
| 論文の数値・図・PDF | `make numbers` / `make figures` / `make paper`（`make paper FINAL=1` は未了結果があると中断） |
| 説明資料PDF・READMEの結果欄・YouTube概要欄 | `make report` / `make readme` / `make youtube`（まとめて `make all-docs`） |
| 全結果の再生成（キャンペーン完了後） | `make finalize` |
| デモ動画（既存の run id から合成） | `make video-plan` → `make video` |
| 研究ごとの実行手順（**表示のみ**。GPU と静かなホストが必要） | `make study-V`、`study-W`、`study-A`、`study-X` など（`make help` に全一覧） |

`study-*` は登録済みコマンドを表示するだけで、キャンペーンを自動では始めません。以下は Makefile が包んでいる個別のコマンドです。

```bash
# 0) 前提: NVIDIA GPU (V100で検証) + docker（nvidia-container-toolkit）。sudoは不要（dockerグループのみ）
export RESCUEMIND_IMAGE=rescuemind:jazzy-next          # build.sh と run.sh が同じ名前を使う（未設定だと両方 rescuemind:jazzy）
bash docker/build.sh                                   # ROS 2 Jazzy + Gazebo Harmonic + PyTorch 2.8/cu126 + transformers 5
#    旧環境（v3.3: torch 2.5.1 / transformers 4.53。図・PDF・テスト用の rm-dev）: docker build --build-arg STACK=v33 -t rescuemind:jazzy docker
# 1) モデル重みを一度だけ取得（以降の実行は HF_HUB_OFFLINE=1）
HF_HUB_OFFLINE=0 bash docker/run.sh python3 -c "from huggingface_hub import snapshot_download as s; s('Qwen/Qwen3.5-9B')"
# 2) テスト（テスト関数 1319 件。数え方は静的で `python3 scripts/count_tests.py`。ROS/Gazebo不要の部分はDockerなしでも実行可）
bash docker/run.sh python3 -m unittest discover -s tests -q
# 3) 1回のAIミッション（Gazebo・ブリッジ・ガード・VLMを自動起動、証拠は outputs/runs/<run_id>/）
V34="--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain"
bash docker/run.sh python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped $V34 \
     --capture-rosbag --instruction '避難所Bで飲み水が足りないそうです'
#    --scene nominal / empty、--hazard-at medicine（火災）、--lighting dim_evening、--distractor-at water
# 4) 事前登録した閉ループ評価（評価D: 42試行。評価Eは experiments/campaign_e_protocol.json） → 図とレポート
bash docker/run.sh python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json \
     --ledger experiments/results/campaign_D_ledger.jsonl -- $V34
bash docker/run.sh python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl
bash docker/run.sh python3 scripts/make_figures.py
```

各事前登録研究の再現コマンド・実行時間・出力・解析スクリプトは [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) にまとめています。
第三者が3段階（GPU なし／GPU・画像単位／閉ループ）で再現するための英語の手順書は [`docs/REPRODUCE.md`](docs/REPRODUCE.md)（`make reproduce-help` で要約を表示）です。

デモ動画用の俯瞰カメラ映像は `--film` で同時収録し、`scripts/make_demo_video.py --plan docs/video_plan.json` で合成します（映像はすべて Gazebo の実レンダリング。合成するのはログ由来の字幕・確率バー・真値軌跡のみ）。

## リポジトリ構成

| パス | 内容 |
|---|---|
| `ros/gazebo_waypoint_mission.py` | ミッション制御ノード（移動・照準・静止確認・新規フレーム取得・VLM確認・停止保持） |
| `ros/guarded_cmd_relay.py` / `rescuemind/velocity_relay.py` | 独立速度ガード |
| `ros/runtime_guard_graph_watch.py` | `/cmd_vel` 発行者のDDSグラフ監視 |
| `ros/odom_evidence_recorder.py` | 独立レコーダ（オドメトリ・速度・**Gazebo真値**） |
| `scripts/local_vlm_server.py` / `rescuemind/local_vision.py` | ローカルVLMサーバ（閉集合スコアリング）と判断ロジック |
| `scripts/v32_orchestrate.py` | スタック起動・準備確認・ミッション・証拠監査の統括 |
| `rescuemind/ground_truth_evidence.py` | Gazebo真値による到着・停止・転倒・乖離の監査 |
| `worlds/` | `rescuemind_test_arena.sdf`（原本）と自動生成した3シーン（正常／取り違え／欠品） |
| `experiments/` | 事前登録（`PREREGISTRATION_*.md`）、プロトコル、開発セット・未使用テストセット T1 の画像、結果台帳、各試行の証拠 |
| `docker/` | 再現環境（Dockerfile・実行ラッパー） |
| `docs/` | 図、[FINDINGS](docs/FINDINGS.md)、レポートPDF、動画の章立て、引継ぎ資料のアーカイブ |
| `scripts/make_figures.py` / `make_report.py` / `make_demo_video.py` | 図・PDF・動画をすべて結果ファイルから再生成（数値の手入力なし） |

`scripts/v0x〜v31_*` や `rescuemind/jev.py` などは引継ぎ前の開発履歴（旧クラウドAPI経路を含む）で、v3.3 の実行経路では使用していません（テストは維持）。

## 限界

保証できること・できないことを、論文と同じ順に書く（「結果待ち」は結果ファイルがまだ無い研究。結果ができると[結果](#結果)の表が先に更新される）。

* 評価はすべて**シミュレーション**です（実機での検証はしていません）。物資の把持・運搬は行わず（現物確認と避難所への接近まで）、Nav2 ではなく既知配置のウェイポイント追従です。
* **保証は相対的**：助言（記憶・他のロボット・依頼文・在庫表）が加えられる危険は、確認そのものの誤許可の上限 ε_any の内側に収まる、というもので、確認の誤りが消えるわけではありません。助言で本物の火のある拠点へ近づくこと（被ばく）や、助言が続くことによる可用性の低下は上限の外です。悪意のある助言の閉ループ評価（A）は結果待ちです。
* **保証の外**：画像に映る文字（評価S：結果待ち）、現実との差（実写真は評価P・P2のみ、倉庫の世界 XD・X：結果待ち）。測るだけで、保証とは言いません。
* **残る弱点**：「物資の陰に一部しか見えない火災」の見逃し（[結果](#結果)の「分かったこと」）。横から見直す工夫で減ったが（評価G）、正面から完全に隠れ横からも小さく写る火は見逃し得る。登録した「T1の誤許可2%未満」の主張は支持されなかった。
* **採用しなかったもの**：2つのAI（評価J）は単独より安全にならず、既定にしていません。
* 評価Eの世界は試行ごとにランダム（照明・物資の位置と向き・妨害物・火災）ですが、**拠点の配置は固定**です。評価D は固定配置の反復で、試行数は独立シーン数ではありません。小道具は単純な形状です。閉ループ評価は 8〜16対と少数で、評価Hの世界の変化は台本どおりです。
* 近距離（約0.9 m 以下）では物資が画面から切れて誤拒否が出ます（実機の想定停止距離は約1.4 m）。
* ROSグラフ監視は認証機構ではなく、実機の安全認証を意味しません。

## ライセンス

MIT（`LICENSE`）。使用モデル：[Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)（Apache-2.0、重みは同梱しない）。
比較実験で [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)・[Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)（Apache-2.0）、
v3.3 の [Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)（Qwen Research License）、[SmolVLM2-2.2B-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct)（Apache-2.0）。

第三者の部品（モデル・データセット・フォント・音声・ワールド）の一覧、ライセンス、守るべき条件は [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)。モデルの重み・データセットの画像・フォント・音声は同梱していません。
**Qwen2.5-VL-3B-Instruct は非商用（研究）限定**です。動画のナレーション：VOICEVOX:四国めたん
