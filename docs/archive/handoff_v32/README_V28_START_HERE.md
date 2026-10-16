# RescueMind v2.8：ここから開始

**2026-10-16 / v2.8.0 / TypeSafe Jev 1.14.0 必須・Qwen3.8-Omni-Flash**

作品の動作：差動二輪で指定物資拠点に到達→物資棚へ回転→物理静止確認→**新規画像2枚＋Gazebo `/clock`との時刻整合**→JevとQwen両方が期待物資を認めたら避難所Bへ接近。誤物資／欠品／画像異常は停止。物資把持・実運搬やNav2経路再計画は実装していません。

**最初に実行**（Ubuntuまたはこのパッケージを展開できるLinux）。

```bash
cd rescuemind_v28
python3 -m pip install -e .
bash scripts/v28_verify.sh
python3 scripts/v28_clock_campaign.py
```

この時点で分かることはPython/模擬ROS/静的SDFの整合性だけです。時計ゲートが本番画像を不必要に拒否しないかは実Gazeboで調整する必要があります。

**Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic**：

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v28_orchestrate.py --plan --scenario motion-check --scene nominal
python3 scripts/v28_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

**API環境（秘密値はファイルやGitHubに残さずシェルで設定）**：

- `TYPESAFE_API_KEY`：必須JeV API資格情報。`rescuemind/jev.py` の画像API仕様を実接続で確認。
- `DASHSCOPE_API_KEY`：Qwen3.8の資格情報。
- `DASHSCOPE_BASE_URL`：公式が案内する地域・Workspaceに一致するHTTPS URL。

`--run` では実API呼出しが生じるため費用に注意。続いて：

```bash
python3 scripts/v28_orchestrate.py --run --scenario live --scene nominal \
  --capture-rosbag --instruction "避難所Bに飲料水を届けて"
python3 scripts/v28_orchestrate.py --run --scenario live --scene swapped \
  --capture-rosbag --instruction "避難所Bに飲料水を届けて"
python3 scripts/v28_orchestrate.py --run --scenario live --scene empty \
  --capture-rosbag --instruction "避難所Bに飲料水を届けて"
```

正常系では `outputs/runs/<16桁ID>/stack_result.json` が `COMPLETED`、意図した拒否では `COMPLETED_EXPECTED_DENIAL`、通信異常などでは `FAILED` が期待されます。いずれも**独立オドメトリ・画像品質・シミュレーション時計監査が必要**です。外部APIが失敗しただけなら認識成功とみなさないでください。

**30試行の管理**：`experiments/v23_locked_protocol.json` を使用し、完了したv2.8実行のみ以下へ登録。

```bash
python3 scripts/v28_register_trial.py --trial-id <事前登録ID> --run-dir outputs/runs/<16桁ID>
```

以前の `scripts/v24_register_trial.py` は履歴再現用で、**v2.8の時計証拠を強制しない**ため、これからの成果登録には使用しないでください。

**審査員向け提出チェック**：実Gazebo録画1〜3分 MP4（倍速は明記）、レポートPDF `説明資料_PAI最終課題_omnicampusアカウント名.pdf`、public GitHub全コード、YouTube最低限定公開URL、OmniCampusフォーム。締切 2026-11-02 10:00 JST。氏名・所属・メール・認証情報を映像／PDF／コードに残さない。PDFドラフトはまだ提出版ではありません。

実装上の根拠・残課題：`docs/V28_AWARD_STRATEGY_AND_PRIMARY_SOURCES.md`。テスト：`verification/v28/verification.json`。検証可能な主張と未検証事項を必ず分離してください。
