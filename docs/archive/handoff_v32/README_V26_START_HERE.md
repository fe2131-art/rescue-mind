# RescueMind v2.6 — 最初に読むガイド（2026-10-16）

## 先に結論

**今回の修正:** 棚への方位合わせだけでは撮影姿勢が安定しているとは限らないため、ROS `nav_msgs/Odometry` の **実測速度（twist）＋位置・ヨー角の変化**から、最低0.65秒／4サンプル連続の静止を確認し、そのあとに取得した新規カメラ画像のみをJev＋Qwenに入力します。静止が確立しない場合／判定中に動いた場合は**ミッション失敗・走行禁止**です。これはシミュレータ上の検証設計であり、安全認証済み停止ではありません。

**作品の正確な機能:** 自然言語の物資指示→差動二輪ロボットが物資拠点へ移動→棚へ向く→静止確認→ROSカメラ画像→**TypeSafe Jev 1.14.0（必須）＋Alibaba Cloud Qwen3.8-Omni-Flash** の二重判断→正常なら避難所Bへ／不適合なら留まる。**物資をつかむ、運ぶ、手渡す機能は実装されていません**。Nav2を使ったこのワールドでの経路再計画も未実証です。

## 1. ROS不要のオフライン検証

```bash
cd rescuemind_v26
python3 -m pip install -e .
bash scripts/v26_verify.sh
```

- `verification/v26/verification.json`：統合検証概要
- `verification/v26/unittest.log`：全自動テスト
- `verification/v26/synthetic_stationary_campaign.json`：人工12条件の移動・停止注入
- `verification/v26/synthetic_stationary_traces.csv`：人工オドメトリ時系列
- `docs/V26_AWARD_STRATEGY_AND_RESEARCH.md`：評価軸別戦略・一次情報・制約

## 2. Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v26_orchestrate.py --plan --scenario motion-check --scene nominal
python3 scripts/v26_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

まずROSトピック `/clock`, `/odom`, `/scan`, `/camera` とGazebo Transportを確認してください。`motion-check`は**AIを使わない走行診断**で、最終課題のAI実演としては提出できません。

## 3. 実JeV/Qwenの現地判断（キーはファイルに保存しない）

```bash
export TYPESAFE_API_KEY='＜自分のキー＞'
export DASHSCOPE_API_KEY='＜自分のキー＞'
export DASHSCOPE_BASE_URL='https://＜利用するAlibabaワークスペース＞.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1'
python3 scripts/v26_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

実験条件を `--scene swapped` と `--scene empty` に変更すると、同一照明・経路・センサー設定で入れ替え／欠品を試せます。`nominal` は避難所到達を、その他は「Jev＋Qwen拒否、独立ROSの静止観測、正常な拒否」の完了を確認します。

**実行ログの必須順序:** `camera_aim_aligned` → `checkpoint_stationary_verified` → `checkpoint_frame` → `checkpoint_decision`。新しい `v26_stationary_evidence.py` はこの順序・静止閾値・フレームのSHA-256を監査し、既存の独立移動証拠と組み合わせます。試行が完了しても、このイベントがない場合は実験成功として登録しません。

## 4. 優秀賞の「証拠」を撮る

1. 正常の実Gazebo映像（全行程）、棚へ回頭→静止→カメラ画像→二重AI判断→避難所Bへ移動。
2. 誤配置・欠品の実Gazebo映像、AI拒否と車体停止（API通信エラーによる停止と混同しない）。
3. 30試行の事前登録 `experiments/v23_locked_protocol.json` に従い、各試行の実画像とログを保存。母数と欠測も集計。
4. 1〜3分の動画をYouTube（限定公開以上）に上げ、公開GitHub URLとPDFをOmniCampusへ提出。氏名・所属・メール・APIキーは一切載せない。締切 **2026-11-02 10:00 JST**。

## 5. 未検証の重大事項

この配布物を作った環境に **ROS 2 / Gazebo / 外部APIキーはありません**。従って実Gazebo物理走行、Jev・Qwenの実API画像判定、ロボット動画、実画像30試行は**未達**です。人工時系列への全件一致は実環境での安全・認識精度を保証しません。閾値はGazebo実測に基づき調整が必要です。
