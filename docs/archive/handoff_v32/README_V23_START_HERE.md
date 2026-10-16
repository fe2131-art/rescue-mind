# RescueMind v2.3 | 実行・評価・提出準備

**結論：まだ提出可能な完成作品ではありません。** このZIPは、課題の「AIを使ってロボットが実行した映像」が完成するまでの研究・実装パッケージです。実Gazebo走行・Jev/Qwen実API・1〜3分MP4は本環境では未検証／未制作です。

## v2.3の改善（v2.2からの追加）

1. **事前登録プロトコル**：同じGazebo環境でnominal・swapped・emptyの3シーン、水・医療物資の2指示、各5反復＝30試行。乱数seed=20261016で試行順を決定。実験シーン以外の照明・ロボット・センサー・経路設定が同一であることをSDF静的検査。
2. **Jev必須**：`jev-1.14.0`の画像判定を必須とし、Qwenの固定モデルは`qwen3.8-omni-flash`。`jev-latest`や旧モデルへの自動フォールバックなし。
3. **厳密な集計**：同じ試行ID、同じ画像、変更された正解ラベル、欠落した反復、模擬入力、モデルID違いは拒否する。途中結果は明示的な`--allow-partial`が必要。
4. **安全性とデータ科学**：誤許可率だけでなく、正常シーンを誤って拒否する率・カバレッジ・遅延を併記。二重モデルの優越性は仮説であり、実測されていない。共有する3つのシーン・同一カメラ条件は統計上独立な実験母集団ではなく、Wilson区間は**記述的**である。
5. **旧機能維持**：ROS 2、Gazebo、独立速度ガード、シミュレーション時刻、独立ROS軌跡、Jev→次区間の許可・拒否と、3シーンSDF比較は引き継ぐ。

## 最短の起動順

```bash
cd rescuemind_v23
python3 -m pip install -e .
bash scripts/v23_verify.sh
bash scripts/check_ubuntu_ros.sh
python3 scripts/v22_orchestrate.py --plan --scenario motion-check --scene nominal
```

Ubuntu 24.04＋ROS 2 Jazzy＋Gazebo Harmonicの準備後、**まず非AIの車輪走行**：

```bash
python3 scripts/v22_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

次にGazeboカメラが物資を確かに写しているか目視確認し、Jev/QwenのAPIキーを安全な環境変数で設定。実際のAPI呼び出しを行う場合のみ：

```bash
python3 scripts/v22_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

**実験順序を事前に固定**（この処理自体はROS/APIを実行しません）：

```bash
python3 scripts/v23_plan_experiment.py --repetitions 5 --seed 20261016
cat experiments/v23_commands.sh
```

`experiments/v23_locked_protocol.json`は試行IDと正解・期待動作を含む研究者用ラベルであり、**どちらのVLMへのプロンプトにも渡してはいけません**。連続撮影した同一画像を独立試行として増やすことも避けてください。条件・乱数を固定しただけでは独立な一般化性能を推定できません。

## 実モデル結果の取得・分析

Gazeboの物資画像と通路画像を別々に保存して、人間が画像上の物資と障害物を確認・注釈したうえで次を実施します（APIが必要）：

```bash
python3 -m rescuemind.record_real_case \
 --supply-image /path/to/supply.png \
 --corridor-image /path/to/corridor.png \
 --expected water --truth-supply water --truth-scene clear \
 --id R001 --qwen-model qwen3.8-omni-flash \
 --output outputs/v23_real_captures.jsonl
```

上記の`R001`と期待ラベルは**必ず`experiments/v23_locked_protocol.json`の該当行で置き換え**ます。計画した画像・指示と違う場合はその試行を欠測として報告し、ラベルで帳尻合わせしません。API出力から作ったJSONLの`real_model:true`は自己申告フィールドであり、通信の真正性証明ではありません。可能であれば実際のリクエスト・レスポンスとAPI利用記録を別途照合してください。個人情報や秘密情報は公開しません。

```bash
python3 scripts/v23_evaluate_captures.py \
  --protocol experiments/v23_locked_protocol.json \
  --captures outputs/v23_real_captures.jsonl \
  --out outputs/v23_real_metrics.json
```

30件揃わない限り終了コード2で拒否します。途中経過を見たい場合のみ `--allow-partial` を付けると `PRELIMINARY_INCOMPLETE` を明記したレポートを作れます。数値を研究成果として記載する前に、人間による画像ラベルのレビューが必須です。

## 合格・優秀賞のための最後のゲート

- [ ] 実GazeboでAI判断→ロボットの動作継続／停止を確認した実行映像
- [ ] 最終MP4は60〜180秒、倍速使用時は倍率を明記
- [ ] 実画像・実API出力・停止理由・独立ROS軌跡・必要に応じてROS bagを対応付け
- [ ] GitHub public、説明資料PDF、YouTube最低限定公開のURLをOmniCampusに提出
- [ ] レポート名 `説明資料_PAI最終課題_omnicampusアカウント名.pdf`
- [ ] 氏名・所属・メール・APIキー等を映さない／コミットしない
- [ ] 締切は2026年11月2日（月）午前10時（JST）

ここでいう物資配送は物理把持・積載を伴わず「現地で正しい物資を確認し、避難所に到達する」ことです。詳細は `docs/V23_AWARD_STRATEGY.md`、`docs/V23_SOURCE_RESEARCH.md`。
