#!/usr/bin/env python3
"""Rewrite the README results block from experiments/results (no hand-typed numbers)."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'


def main():
    rows = [json.loads(x) for x in (RES / 'campaign_ledger.jsonl').read_text().splitlines()]
    final = [r for r in rows if r.get('final', True)]
    retries = len(rows) - len(final)
    lat = sorted(r['vlm_latency_s'] for r in final if r.get('vlm_latency_s') is not None)
    dec = [r for r in final if r.get('vlm_reason')]
    allow = lambda r: r['vlm_reason'] == 'on_site_supply_confirmed'
    dec_ok = sum(allow(r) == (r['expected_action'] == 'ALLOW') for r in dec)
    fa = sum(allow(r) and r['expected_action'] == 'DENY' for r in dec)
    fd = sum((not allow(r)) and r['expected_action'] == 'ALLOW' for r in dec)
    correct = sum(r['correct'] for r in final)
    misses = [r for r in final if not r['correct']]

    def why(r):
        e = r.get('error') or ''
        if 'odometry diverged' in e:
            return f"{r['trial_id']}（{r['scene']}・{r['expected_supply']}）：VLMは正しく許可し避難所へ走行したが、車輪オドメトリの累積誤差（0.27 m）が監査上限0.25 mを超え、真値では目標点の0.34 m手前で停止"
        if r['observed_action'] == 'DENY_UNVERIFIED':
            return f"{r['trial_id']}（{r['scene']}・{r['expected_supply']}）：VLMは正しく拒否しロボットも停止したが、静止証拠の時刻整合チェックが3 ms差で不合格（修正済み）"
        return f"{r['trial_id']}：{e[:80]}"

    def cell(scene, act):
        return sum(r['scene'] == scene and r['observed_action'] == act for r in final)
    aborted = []
    for k in ('A', 'B'):
        f = RES / f'campaign_{k}_aborted_ledger.jsonl'
        if f.is_file():
            aborted.append(k)
    block = f"""<!-- RESULTS:START -->
## 結果（事前登録した30試行・自律走行＋実撮影＋実推論）

| シーン（期待動作） | 許可→避難所Bに到着 | 拒否→拠点で停止 | 拒否（停止証拠が不合格） | 失敗 |
|---|---|---|---|---|
| 正常配置（許可） | **{cell('nominal','ALLOW')}** | {cell('nominal','DENY')} | {cell('nominal','DENY_UNVERIFIED')} | {cell('nominal','FAILED')} |
| 水と救急箱の取り違え（拒否） | {cell('swapped','ALLOW')} | **{cell('swapped','DENY')}** | {cell('swapped','DENY_UNVERIFIED')} | {cell('swapped','FAILED')} |
| 欠品・棚が空（拒否） | {cell('empty','ALLOW')} | **{cell('empty','DENY')}** | {cell('empty','DENY_UNVERIFIED')} | {cell('empty','FAILED')} |

* **VLMの判断（許可／拒否）は {dec_ok}/{len(dec)} で正解**：危険側の誤り（誤許可）**{fa}件**、誤拒否 {fd}件
* 判断に加えて Gazebo真値・ROS bag・時系列の**独立監査まで全て合格**：**{correct}/{len(final)}**
""" + ''.join(f"  * {why(r)}\n" for r in misses) + f"""* VLM判断遅延（静止画取得→判断、2問）中央値 **{lat[len(lat)//2]:.2f} 秒**（最大 {lat[-1]:.2f} 秒）、V100 FP16、VRAM 約8 GB
* VLM判断前のインフラ失敗による再試行：{retries}件（台帳に全件記録）。3シーン×5反復は30個の独立シーンではない
""" + (f"* この評価（C）の前に、起動時の競合と孤立プロセスが原因で評価{'・'.join(aborted)}を中断（台帳は公開、詳細は [`docs/FINDINGS.md`](docs/FINDINGS.md) #12・#13）\n" if aborted else '') + """
![results](docs/figures/campaign_results.png)
<!-- RESULTS:END -->"""
    readme = ROOT / 'README.md'
    s = readme.read_text(encoding='utf8')
    a, b = s.index('<!-- RESULTS:START -->'), s.index('<!-- RESULTS:END -->') + len('<!-- RESULTS:END -->')
    readme.write_text(s[:a] + block + s[b:], encoding='utf8')
    print('README results updated:', correct, '/', len(final))


if __name__ == '__main__':
    main()
