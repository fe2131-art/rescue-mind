# GPU/Linux引き継ぎガイド — RescueMind v3.2 local-first

**引き継ぎ日：2026年10月16日｜対象：Tesla V100 32GB / Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic**

## A. プロジェクトの正確な到達状況

課題名は「AI×ロボティクスによる創造的タスクの実現」。加点要素は **創造性、技術力、実用性、表現力** です。AIは推論だけでも要件を満たします。コード一式、実際のロボット動画（1〜3分）、レポートが必要。締切 **2026年11月2日（月）10:00 JST**。

| 項目 | 状態 | 合否判定上の意味 |
|---|---|---|
| 自然言語で水／医療物資・避難所Bを指定 | 実装済／CPUテスト済 | 文面の誤解釈は拒否 |
| Gazeboでの差動二輪ロボット、3シーンSDF | 作成済／静的・理想運動学試験済 | 実レンダリング・車輪動作は未検証 |
| ロボット移動・棚への向き合わせ・静止確認 | ROSコード／模擬ROS試験済 | 実物理演算では未検証 |
| カメラ2枚品質・撮影鮮度・Gazebo時刻照合 | 実装済／模擬故障試験済 | 実Gazeboとの動作確認は未検証 |
| **ローカルQwen2.5-VL-3B画像推論** | **実装済・CPU側の偽サーバ／API整合性試験済** | **V100でのモデルロード・実推論は未検証** |
| ローカルSmolVLM2-2.2Bとの2モデル合議 | オプションの実装・モック試験済 | 実GPU上の同時ロードは未検証 |
| Jev 1.14.0＋クラウドQwen3.8 | 旧コード保持 | **ローカル優先経路では一切使用しない** |
| 独立速度ガード、publisher監視、ROS観測 | 実装済・模擬試験済 | 安全認証を意味しない |
| 正常完走／意図した拒否／障害の区別 | オフラインテスト済 | 実環境の分類は未検証 |
| ROS bag収録と独立ログ監査 | コードあり・録画終了のモック実験済 | 本物のrosbag2収録は未検証 |
| 30試行の比較計画 | 3シーン×2物資×5反復・ID固定済 | 実画像による測定は0試行 |
| 提出用MP4／GitHub／YouTube／最終PDF | 手順・ドラフトのみ | **未完成・未提出** |
| 物資把持・実運搬 | **未実装** | 配達完了と表現しない |

## B. モデル／メモリ構成（V100 32GB）

**標準・最軽量：** `Qwen/Qwen2.5-VL-3B-Instruct` を **FP16 / eager attention / 約640ピクセル以内の入力**で利用。モデルの3B言語部分だけでもFP16の重みは概算6GBで、画像エンコーダ・実行時KVキャッシュ・PyTorch・GazeboのGPUメモリが追加されます。**32GBへの収まりは推定であり実測保証ではありません。**

- `--local-mode single`：同じ3B VLMへ異なる2つの質問を送り、双方が正しい物資で一致した場合のみ続行。**単一モデルの二重確認であり、独立した2モデルではありません。** 通信先は127.0.0.1:8765。
- `--local-mode dual`：Qwen2.5-VL-3B＋SmolVLM2-2.2Bを別プロセス・別モデルで判定。第2サーバーは127.0.0.1:8766。**GPUメモリ／起動時間の増加、実互換性未確認**につき標準では使わない。
- BF16、FlashAttention2、vLLMの最新CUDA 12.8/13系は使わず、V100のVolta世代に合うFP16の標準Transformers推論にする。PyTorch 2.5.1 + CUDA 12.1 wheelを固定（現地ドライバ対応を要確認）。
- 初回モデル重み取得時のみHugging Faceへネット接続。`ModelWorker`は`local_files_only=True`でロードするため、**ライブ時にクラウド推論や自動ダウンロードへ移行しない**。重みファイルはZIPに含まれていません。

## C. Ubuntuで初日に実施する順番

### 1）GPU・ROS・Gazebo環境（Ubuntu 24.04）

```bash
nvidia-smi                          # V100 32GB / driver / 空きGPUメモリ
lsb_release -a                     # Ubuntu 24.04
ls /opt/ros/jazzy/setup.bash
source /opt/ros/jazzy/setup.bash
ros2 --help
gz sim --versions
```

ROSが未導入なら公式 `https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html`、Gazeboは `https://gazebosim.org/docs/harmonic/ros_installation/` を参照。`ros-jazzy-ros-gz` と `ros-jazzy-rosbag2` が必要。

### 2）ZIPを展開 → ROS連携のvenv → ローカルモデル

```bash
unzip RescueMind_v3.2_Local_V100_32GB_Final_Handoff.zip
cd rescuemind_local_v32
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/install_local_vlm_v100.sh    # 初回のみモデル重みDL、CUDA PyTorchインストール
source .venv/bin/activate
python3 scripts/local_gpu_preflight.py --mode single
bash scripts/v32_verify.sh
```

プリフライトに `ready: true` が必要。失敗したらモデル起動やロボット運行を始めない。**APIキー不要**。モデルロードエラー時はCUDAバージョン、ドライバ、`torch.cuda.get_device_capability() == (7,0)`、transformersバージョン、Hugging Faceキャッシュを確認。

### 3）モデル単体の本物のローカル推論（Gazebo前）

端末A：

```bash
source .venv/bin/activate
HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen2.5-VL-3B-Instruct --port 8765
```

端末B：

```bash
source .venv/bin/activate
curl -s http://127.0.0.1:8765/health
python3 scripts/v32_local_smoke.py --image fixtures/supply_schematic.jpg --expected water \
    --out outputs/local_v100_smoke.json
```

`fixtures/supply_schematic.jpg`は**接続テスト用の模式図**で、識別精度評価には使わない。本当の評価にはGazebo撮影画像を使う。`--mode single`の両質問結果、GPUメモリと推論秒数を記録する。終わったら端末AをCtrl-Cで停止（自動オーケストレータとポートを競合させない）。

### 4）AIを使わずにGazebo走行を最初に完走

```bash
python3 scripts/v32_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag
python3 scripts/v32_orchestrate.py --run  --scenario motion-check --scene nominal --capture-rosbag
```

**合格条件：** 起動成功、`/odom`、`/scan`、`/camera`、`/clock`、速度ガードが正常、物資拠点→避難所の独立軌跡監査が通過、ROS bagがメタデータまで確定。失敗時は `outputs/runs/<run_id>/stack_result.json` → `readiness_last.txt` → `*.log` の順に確認。AIなし走行は**最終課題のAI動作実証ではない**。

### 5）ローカルVLMを伴う本命ミッション

```bash
# まず起動計画。モデルサーバーはv32側が自動起動します。
python3 scripts/v32_orchestrate.py --plan --scenario live --scene nominal --local-mode single --capture-rosbag
# 正常配置
python3 scripts/v32_orchestrate.py --run  --scenario live --scene nominal --local-mode single --capture-rosbag --instruction '避難所Bに飲料水を届けて'
# 誤物資と欠品: ローカルVLMが拒否して停止するのが期待動作
python3 scripts/v32_orchestrate.py --run  --scenario live --scene swapped --local-mode single --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v32_orchestrate.py --run  --scenario live --scene empty   --local-mode single --capture-rosbag --instruction '避難所Bに飲料水を届けて'
```

分類は `COMPLETED`（正常許可＋独立到達証拠）、`COMPLETED_EXPECTED_DENIAL`（拒否＋拒否後停止・独立観測）、`FAILED`（VLM解析・センサー・録画・走行等の失敗）。**VLMがエラーで止まっただけなら拒否成功ではない**。各試行で `mission.json` の `run_type` は `local_vlm_live_mission`、`checkpoint.backend=LOCAL_ONLY_NO_CLOUD_API` を確認する。

### 6）余力があれば2種類の別モデル（発展実験）

```bash
source .venv/bin/activate
python3 -c 'from huggingface_hub import snapshot_download; snapshot_download("HuggingFaceTB/SmolVLM2-2.2B-Instruct")'
python3 scripts/local_gpu_preflight.py --mode dual
python3 scripts/v32_orchestrate.py --run --scenario live --scene nominal --local-mode dual --capture-rosbag --instruction '避難所Bに飲料水を届けて'
```

VRAM不足・モデル互換性問題なら**標準のsingleに戻す**。dualの方が安全・高精度とは実測前には断定しない。

## D. 優秀賞向けの実験・プレゼン

`python3 scripts/v32_print_trial_commands.py`で**事前固定済み30試行**を表示。試行ID／run_id／SDF SHA-256／ROS保存画像のSHA／使用モデル／推論秒数／完走・拒否・故障を記録。3シーンの5反復は独立シーン30個ではないので成功率の過大主張を避ける。実測の誤許可率・誤拒否率・遅延を明示し、観測不足は欠測として別集計する。

動画は1～3分で、①作品の目的10秒、②Gazebo正常シーン30秒、③誤物資拒否25秒、④欠品拒否20秒、⑤AI判断＋独立制御ガード・結果20秒を目安とする。ROS / Gazeboの実画面を撮り、**モック画像や模式図を実実行映像として使用しない**。倍速なら動画内に明記。

## E. 提出手順（課題原文の記載）

- Public GitHub：コード一式。`.env`、認証トークン、個人情報、ロボット実行時の私的画像を公開前に確認。
- PDFレポート：`説明資料_PAI最終課題_omnicampusアカウント名.pdf`。この引き継ぎPDFは提出完成版ではない。実測の比較表と動画キャプチャを反映して確定。
- YouTube：`PAI最終課題_omnicampusアカウント名`、公開または限定公開（最低条件）、子供向け／年齢制限は「いいえ」。動画URLをomnicampusに提出。
- 提出期限：**2026-11-02 10:00 JST**。氏名・所属・メールなどの個人情報はコード・レポート・動画へ載せない。

## F. 判断の根拠（外部公式情報。実走行ではない）

- Qwen2.5-VL-3B-Instruct モデルカード： https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
- SmolVLM2-2.2B-Instruct モデルカード： https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct
- Hugging Faceマルチモーダルチャットテンプレート： https://huggingface.co/docs/transformers/en/chat_templating_multimodal
- NVIDIA Tesla V100 32GB仕様： https://images.nvidia.com/content/pdf/vgpu/data-sheet/nvidia-v100.pdf
- PyTorch Volta と CUDA wheel： https://dev-discuss.pytorch.org/t/dropping-volta-support-from-cuda-12-8-binaries-for-release-2-11/3290
- Volta BF16非推奨の根拠： https://discuss.pytorch.org/t/current-cuda-device-does-not-support-bfloat16-please-switch-dtype-to-float16/201564/2
- ROS/Gazebo推奨組合せ： https://gazebosim.org/docs/harmonic/ros_installation/

**この引き継ぎZIPはコードのみで、モデルの重みを含みません。上記のモデル使用条件・ライセンスをGitHub公開前に確認してください。**
