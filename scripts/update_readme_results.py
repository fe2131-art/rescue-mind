#!/usr/bin/env python3
"""Rewrite the README results block from experiments/results (no hand-typed numbers) — v3.4 (campaign D)."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
GROUP = {'nominal': ('正常配置', '配達'), 'swapped': ('水と救急箱の取り違え', '別拠点を探索して配達'),
         'empty': ('欠品（両拠点とも空）', '両拠点で確認して停止'), 'fire': ('拠点の裏で火災', '探索せず即停止'),
         'dim': ('夕方の暗い照明', '配達'), 'box': ('空の台に段ボール箱', '停止')}
OBS = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止', 'DENY_HAZARD': '危険で停止',
       'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}


def main():
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/v34_protocol.json').read_text())['trials']}
    rows_all = [json.loads(x) for x in (RES / 'campaign_D_ledger.jsonl').read_text().splitlines()]
    rows = [r for r in rows_all if r.get('final', True)]
    for r in rows:
        t = proto[r['trial_id']]
        r['group'] = ('fire' if t.get('hazard_at') else 'dim' if t.get('lighting') == 'dim_evening'
                      else 'box' if t.get('distractor_at') else t['scene'])
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    fa = sum(r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r['expected_action'] in ('DENY', 'DENY_HAZARD')
             for r in rows)
    ok = sum(r['correct'] for r in rows)
    lines = ['| シナリオ | 期待する行動 | 期待どおり | 実際の行動 |', '|---|---|---|---|']
    for g, (ja, want) in GROUP.items():
        rs = [r for r in rows if r['group'] == g]
        if rs:
            c = sum(r['correct'] for r in rs)
            got = '、'.join(f'{OBS.get(k, k)} {v}' for k, v in Counter(r['observed_action'] for r in rs).items())
            lines.append(f'| {ja} | {want} | **{c}/{len(rs)}** | {got} |')
    misses = [r for r in rows if not r['correct']]
    miss_txt = ''.join(f"  * {r['trial_id']}（{GROUP[r['group']][0]}）：{OBS.get(r['observed_action'], r['observed_action'])}"
                       f"{' — ' + (r.get('error') or '')[:90] if r.get('error') else ''}\n" for r in misses)
    block = f"""<!-- RESULTS:START -->
## 結果：事前登録した閉ループ評価（評価D・v3.4、{len(rows)}試行）

Qwen3.5-9B（ローカル・V100）、回復探索・状況報告・LLM指示理解をすべて有効にした構成で、試行ごとに全スタックを新規起動。

{chr(10).join(lines)}

* 期待どおりの行動 **{ok}/{len(rows)}**、誤った物資・火災の拠点からの配達（誤許可）**{fa}件**
{miss_txt}* 判断遅延（静止画取得→判断）中央値 **{lat[len(lat) // 2]:.2f} 秒**（最大 {lat[-1]:.2f} 秒）
* 成功・停止はいずれも Gazebo 真値軌跡・ROS bag・判断の再計算・（回復時は）探索手順で独立に監査（[`experiments/results/`](experiments/results/)）
* VLM判断前のインフラ失敗による再試行：{len(rows_all) - len(rows)}件（台帳に全件記録）。同じワールドの反復であり独立シーン数ではない
* 前バージョン v3.3（評価C、Qwen2.5-VL-3B、回復探索なし）の結果と経緯は [`docs/IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md)

![results](docs/figures/campaign_d_results.png)
<!-- RESULTS:END -->"""
    readme = ROOT / 'README.md'
    s = readme.read_text(encoding='utf8')
    a, b = s.index('<!-- RESULTS:START -->'), s.index('<!-- RESULTS:END -->') + len('<!-- RESULTS:END -->')
    readme.write_text(s[:a] + block + s[b:], encoding='utf8')
    print('README results updated:', ok, '/', len(rows))


if __name__ == '__main__':
    main()
