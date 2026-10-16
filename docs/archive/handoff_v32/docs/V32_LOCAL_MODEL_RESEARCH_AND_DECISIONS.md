# v3.2 ローカル推論・V100研究記録（2026-10-16）

## A. 課題原文に基づく位置づけ
- 課題名：AI×ロボティクスによる創造的タスクの実現。
- ①創造性：同じ指示でも物資が正しい／入れ替え／欠品で行動が変わる。
- ②技術力：ローカルマルチモーダルVLM＋ROS 2 / Gazebo、向き合わせ、静止、画像品質、独立速度ガード、ROS bag。
- ③実用性：不確実な観測・AI拒否・故障を区別して停止。
- ④表現力：実映像とロボットの独立観測、ログを並べて示す。
- 課題原文は `docs/Physical-AI応用1講座-最終課題_10-8版.txt` に保存。

## B. 採用モデルと外部一次資料
- 標準：Qwen/Qwen2.5-VL-3B-Instruct（公式モデルカード） https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
- オプションの2モデル合議：HuggingFaceTB/SmolVLM2-2.2B-Instruct https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct
- 画像＋文字を処理する Transformers API https://huggingface.co/docs/transformers/en/chat_templating_multimodal
- Volta V100（32/16GB HBM2） https://images.nvidia.com/content/pdf/vgpu/data-sheet/nvidia-v100.pdf
- PyTorchのVolta対応と新CUDA wheel互換性 https://dev-discuss.pytorch.org/t/dropping-volta-support-from-cuda-12-8-binaries-for-release-2-11/3290
- BF16はV100でネイティブ推奨されず、FP16を採用 https://discuss.pytorch.org/t/current-cuda-device-does-not-support-bfloat16-please-switch-dtype-to-float16/201564/2
- ROS/Gazeboの推奨組合せ https://gazebosim.org/docs/harmonic/ros_installation/

## C. コード上の構成と限界
- `scripts/v32_orchestrate.py` が必要なローカルVLMプロセスを127.0.0.1で起動。`--scenario motion-check` ではモデルを起動しない。`--scenario live` でROS撮影→ローカル分類→続行／拒否。
- `scripts/local_vlm_server.py` が PyTorch FP16 + eager attention の Transformers 推論、`local_files_only=True` で学習済み重みをロード。ライブ運転中に自動DLしない。
- `rescuemind/local_vision.py` は loopback URL・画像SHA・モデルID・JSONカテゴリに制約。偽応答・不一致・推論エラー・誤物資は停止。
- `rescuemind/local_run_audit.py` は保存された回答を再計算する。独立ROS軌跡・時刻・カメラ・監視イベントも各既存監査で確認。
- 標準 single の2回答は **同じQwen2.5-VL-3B** からの二回の出力。独立モデル合議とは扱わない。
- 旧クラウド構成は`scripts/v31_orchestrate.py`に残存。ローカルv32経路ではTypeSafe、DashScope、リモートHTTPを利用しない。
- **未検証**：モデル重みロード、V100推論速度・VRAM実測、実Gazebo車輪走行、rosbag2実記録、実画像における分類の誤許可・誤拒否、提出用MP4。
- **未実装**：物資把持・輸送、実機の安全認証、Nav2動的再計画の本シーン実証。

## D. メモリの概算と注意
- 3Bパラメータ×2バイト≒6GBは **重み部分のみの概算**。視覚エンコーダ・KVキャッシュ・GPU演算領域・Gazebo描画メモリを除く。モデルのGPU実メモリは測定していない。
- 2.2B追加モデルはFP16重み概算でさらに4.4GB前後、総GPUメモリが32GBに収まることを保証しない。
- V100向けの互換性を優先して PyTorch2.5.1 cu121、transformers4.53.3 のセットを導入スクリプトで選択。ただし**この組み合わせをV100実GPUで走らせてはいない**。不適合ならLinuxでバージョンと個別エラーを記録して調整する。
- GPU推論重みは ZIP未同梱。ネット接続で初期キャッシュ取得が必要。必ずモデルカードのライセンスを確認。

## E. 再現可能なオフライン検証
- `bash scripts/v32_verify.sh`：506件のPythonテスト、人工HTTPモック・模擬ROS・構成静的検査、3シーン＋dual＋非AIの実行計画、30試行計画。実API推論、実GPU検証ではない。
- `python3 scripts/local_gpu_preflight.py --mode single`：この作業コンテナではCUDA未導入のため、意図どおり `ready: false`、終了コード2となった。Linuxへ移したら`ready: true`を達成すること。
- Linux本番の実測結果を取得したら記録に残し、未実施を成功数に入れない。
