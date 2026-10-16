# RescueMind v2.4 | まずここから（Ubuntu 24.04 + NVIDIA GPU）

**現状：本ZIPはオフライン検証済みの研究実装であり、提出済みの完成作品ではありません。** 現環境では `ros2` / `gz` / Jev・QwenのAPIキーがなく、実Gazebo物理走行、実モデル推論、60〜180秒MP4は未実施です。

## 1. v2.3からの重要な修正

* 従来は`swapped`/`empty`で **正しくAIが拒否してもプロセス非ゼロ終了＝一般的失敗** とされ、実験成果の集計が困難でした。
* v2.4は拒否判断後に **2.5秒ゼロ速度維持**を試み、その間もLiDAR・カメラ・オドメトリ・速度ガードの監視を継続します。独立ROS観測で静止を確認できた場合だけ`COMPLETED_EXPECTED_DENIAL`と分類します。監視異常、API接続失敗、移動を観測した場合は従来どおり`FAILED`です。
* `v24_register_trial.py`で事前登録試行（R001など）と唯一の実行IDを照合します。モデルバージョン、現地写真のハッシュ、SDFのハッシュ、予定物資と実際の指示、独立移動監査を全部確認します。別試行に同じ画像を再利用する登録も拒否します。
* ROS bagを指定した場合は拒否試行でも収録メタデータの検査を要求します。

## 2. 最小の再現コマンド

```bash
cd rescuemind_v24
python3 -m pip install -e .
bash scripts/v24_verify.sh
bash scripts/check_ubuntu_ros.sh
python3 scripts/v22_orchestrate.py --plan --scenario live --scene swapped
```

**必ず先に**実Gazeboの非AI動作を検証：

```bash
# Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic がインストール済みの場合
# 必要に応じて setup_ubuntu_jazzy.sh を実行し、付属のREADMEを確認
python3 scripts/v22_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

Jev 1.14.0とQwen3.8-Omni-Flashの正規API認証を行い、物資が正しく写ることを目視確認した後に：

```bash
python3 scripts/v22_orchestrate.py --run --scenario live --scene nominal --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene swapped --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene empty --capture-rosbag --instruction '避難所Bに飲料水を届けて'
```

**意図した拒否を表す新しい最終状態**：`COMPLETED_EXPECTED_DENIAL`。`FAILED`は認識成功に数えません。

## 3. 固定された30試行と証拠登録

`experiments/v23_locked_protocol.json` に6条件×5回＝30試行、seed=20261016で実行順が固定されています。順序を変更せず、各試行をUbuntuで実施し、生成された実行フォルダと予定IDを結び付けます。

```bash
python3 scripts/v23_plan_experiment.py --seed 20261016 --repetitions 5
# 例：R001の条件で本当に実行した後、ファイルを指定
python3 scripts/v24_register_trial.py --trial-id R001 \
 --run-dir outputs/runs/<実際の16桁run_id>
```

実行IDの `<...>` は実際の生成名に置換してください。**何も実行していない状態では登録に失敗するのが正しい挙動です。** 登録先`experiments/v24_run_registry.jsonl`は追記専用で、同じ試行ID・同じ実行ID・同じ画像ハッシュの再使用を拒否します。

`v23_evaluate_captures.py`は別系統の、物資画像＋通路画像を入力する**Jev/Qwenモデル比較実験**です。`v24_register_trial.py`は**Gazeboロボットの現地AI判定と移動証拠**です。両者の指標を混同しないでください。

## 4. 締切前の優先順位

1. **10/16〜10/19** 実ROS/Gazebo起動と`motion-check`の成功を得る。できなければROSログを保管し、最小移動に絞る。
2. **10/20〜10/24** Jev＋QwenのAPIを実画像で検証。正配置・入替・欠品の各1例をまず実行。APIエラーと正しい拒否を混同しない。
3. **10/25〜10/29** 追加試行と解析、正常/拒否対照、動画収録。30試行未達なら不足を明記し、集計結果を誇張しない。
4. **10/30〜11/1** 1〜3分MP4、説明PDF、GitHub public、YouTube（限定公開以上）、OmniCampusの投稿内容を確認。
5. **11/2 10:00 JST** 提出締切。個人情報・APIキーをPDF/動画/公開リポジトリへ載せない。

課題名「AI×ロボティクスによる創造的タスクの実現」の加点は創造性・技術力・実用性・表現力。単なるオフラインテストだけでは合格要件となるロボット動画には代わりません。物資把持・運搬は未実装で、正確なタスク範囲は**物資拠点の識別・確認と避難所への移動**です。
