#!/usr/bin/env python3
"""Write docs/video_plan.json (storyboard for make_demo_video.py) from real results — v3.4.

  python3 scripts/make_video_plan.py --deliver <run_id> --recover <run_id> --fire <run_id>

The demo runs are separate `--film` recordings with the same frozen v3.4 configuration as
evaluation D (the evaluation itself ran without the extra overview camera).
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
G, R, W = (60, 200, 120), (240, 80, 80), (236, 241, 248)
OBS_JA = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止', 'DENY_HAZARD': '危険で停止',
          'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}


def campaign_d():
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/v34_protocol.json').read_text())['trials']}
    rows = [json.loads(x) for x in (RES / 'campaign_D_ledger.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r.get('final', True)]
    for r in rows:
        t = proto[r['trial_id']]
        r['group'] = ('fire' if t.get('hazard_at') else 'dim' if t.get('lighting') == 'dim_evening'
                      else 'box' if t.get('distractor_at') else t['scene'])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deliver', required=True)
    ap.add_argument('--recover', required=True)
    ap.add_argument('--fire', required=True)
    ap.add_argument('--repo-url', default='github.com/fe2131-art/rescue-mind')
    a = ap.parse_args()
    runs = {k: json.loads((ROOT / 'outputs/runs' / v / 'mission.json').read_text(encoding='utf8'))
            for k, v in (('deliver', a.deliver), ('recover', a.recover), ('fire', a.fire))}
    rows = campaign_d()
    ok, n = sum(r['correct'] for r in rows), len(rows)
    fa = sum(r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r['expected_action'] in ('DENY', 'DENY_HAZARD')
             for r in rows)
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    grp = {'nominal': '正常配置（配達）', 'swapped': '取り違え（探索→配達）', 'empty': '欠品（停止）',
           'fire': '火災（即停止）', 'dim': '夕方の照明（配達）', 'box': '空の台＋段ボール（停止）'}
    table_rows = []
    for g, ja in grp.items():
        rs = [r for r in rows if r['group'] == g]
        if rs:
            c = sum(r['correct'] for r in rs)
            table_rows.append([ja, [f'{c}/{len(rs)}', G if c == len(rs) else R],
                               '、'.join(f'{OBS_JA.get(k, k)} {v}' for k, v in Counter(r['observed_action'] for r in rs).items())])
    imp = json.loads((RES / 'i08_model_selection.json').read_text())
    sel = next(r for r in imp if r['model'] == 'Qwen3.5-9B')
    old = next(r for r in imp if r['model'] == 'Qwen2.5-VL-3B')
    it_old = json.loads((RES / 'intent_tfidf.json').read_text())['summary']
    it_new = json.loads((RES / 'intent_hybrid_selected_qwen35_9b_i35.json').read_text())['summary']
    d_ins = runs['deliver']['instruction']
    plan = {'parts': [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'image': 'docs/figures/hero_gazebo.png',
         'sub': '現地で「目で確かめてから」届ける災害物資ロボット',
         'body': ['ROS 2 Jazzy × Gazebo Harmonic × ローカルVLM Qwen3.5-9B（Tesla V100）',
                  '映像はすべて Gazebo の実レンダリング（俯瞰カメラ＋ロボット搭載カメラ）。',
                  '※ 走行区間は3倍速、AI判断の区間は等速。速度は常に画面左上に表示します。']},
        {'kind': 'card', 'seconds': 8, 'title': 'なぜ「確かめる」のか', 'sub': '災害時は、在庫表と棚の現物が食い違う',
         'body': ['「水があるはずの棚に救急箱がある」「棚が空」「火災が起きている」——指示どおり運ぶだけのロボットは誤った物資を届けてしまう。',
                  'RescueMind は拠点で止まって現物をローカルVLMで確認し、違えば別の拠点を探し、危険なら止まって人に報告する。']},
        {'kind': 'card', 'seconds': 8, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
         'image': 'docs/figures/architecture.png', 'layout': 'image',
         'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']},
        {'kind': 'mission', 'index': 1, 'total': 3, 'scene': 'nominal', 'title': '言い換えた指示でも理解して配達',
         'run_dir': f'outputs/runs/{a.deliver}', 'fast': 3.0,
         'captions': {'go': f'「{d_ins}」——物資名の無い指示も、ローカルLLMが依頼内容を解釈して出発。',
                      'check': '拠点で静止し、新しいカメラ画像をVLMに2つの選択式質問で確認させます。',
                      'after': '2問とも依頼物資を高確信で確認 → 許可。避難所Bへ（オレンジ線＝Gazebo真値の軌跡）。'}},
        {'kind': 'mission', 'index': 2, 'total': 3, 'scene': 'swapped', 'title': '物資の取り違え → 別拠点を探索',
         'run_dir': f'outputs/runs/{a.recover}', 'fast': 3.0,
         'captions': {'go': f"在庫情報と現物が食い違うケース。「{runs['recover']['instruction']}」",
                      'check': '拠点で現物を確認中……',
                      'search': '依頼の物資ではない → 止まらずに、もう一方の拠点を確認しに行きます。',
                      'after': '別拠点で依頼物資を確認 → 許可して避難所Bへ。判断の経緯はすべて記録・監査されます。'}},
        {'kind': 'mission', 'index': 3, 'total': 3, 'scene': 'nominal', 'title': '火災を検知 → 探索せず停止',
         'run_dir': f'outputs/runs/{a.fire}', 'fast': 3.0, 'hazard_at': 'medicine',
         'captions': {'go': f"拠点の裏で火災が起きているケース。「{runs['fire']['instruction']}」",
                      'check': '物資は正しいが、画像の中に火や煙は無いか？',
                      'after': '火災・煙を検知 → 拒否。危険な場所を探し回らず停止し、状況を報告します。'}},
        {'kind': 'table', 'seconds': 12, 'title': f'事前登録{n}試行：期待どおり {ok}/{n}・誤許可 {fa}件',
         'sub': '毎試行 Gazebo・ROS・VLM を新規起動。Gazebo真値・ROS bag・判断の再計算で独立に監査',
         'header': ['シナリオ（期待）', '期待どおり', '実際の行動'], 'rows': table_rows,
         'notes': [f'判断の遅延 中央値 {lat[len(lat) // 2]:.1f} 秒（静止画取得→判断、V100）。同じワールドの反復であり独立シーン数ではない。']},
        {'kind': 'card', 'seconds': 9, 'title': '最新モデルを調査して公平に比較・選定',
         'sub': 'Qwen2.5-VL-3B（2025-01）→ Qwen3.5-9B（2026-02、Apache-2.0）',
         'image': 'docs/figures/i08_models.png', 'layout': 'image',
         'body': [f"状況説明 {old['explain']} → {sel['explain']}、指示理解（未知の60文）{it_old['correct']} → {it_new['correct']}/60、誤許可・危険な誤受理 0"]},
        {'kind': 'card', 'seconds': 10, 'title': '試行錯誤の記録（v3.3 → v3.4）',
         'sub': '弱点 → 仮説 → 変更 → 計測（Before/After）を docs/IMPROVEMENT_LOG.md に全て記録',
         'image': 'docs/figures/i01_drift.png',
         'body': ['推測航法のずれ 0.16→0.011 m（原因：車輪の円柱接触）', '照明・妨害物・火災の頑健性 169→176/176',
                  '取り違えでも探索して配達、火災では即停止', '日本語の状況報告で人に判断を委ねる']},
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'sub': a.repo_url, 'image': 'docs/figures/hero_gazebo.png',
         'body': ['AIが間違えるとき、ロボットは動かない。無ければ探し、危険なら止まる。',
                  'コード・事前登録・全試行の証拠・再現用Dockerを公開しています。']},
    ]}
    out = ROOT / 'docs/video_plan.json'
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(out)


if __name__ == '__main__':
    main()
