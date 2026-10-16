#!/usr/bin/env python3
"""Write docs/video_plan.json (storyboard for make_demo_video.py) from real results.

  python3 scripts/make_video_plan.py --nominal <run_id> --swapped <run_id> --empty <run_id>

The three demo runs are separate `--film` recordings with the same code as the
30-trial evaluation (the evaluation itself ran without the extra film camera).
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nominal', required=True)
    ap.add_argument('--swapped', required=True)
    ap.add_argument('--empty', required=True)
    ap.add_argument('--repo-url', default='github.com/fe2131-art/rescue-mind')
    a = ap.parse_args()
    rows = [json.loads(x) for x in (RES / 'campaign_ledger.jsonl').read_text().splitlines()]
    final = [r for r in rows if r.get('final', True)]
    correct = sum(r['correct'] for r in final)
    dec = [r for r in final if r.get('vlm_reason')]
    allowed = lambda r: r['vlm_reason'] == 'on_site_supply_confirmed'
    dec_ok = sum(allowed(r) == (r['expected_action'] == 'ALLOW') for r in dec)
    fa = sum(allowed(r) and r['expected_action'] == 'DENY' for r in dec)
    lat = sorted(r['vlm_latency_s'] for r in final if r.get('vlm_latency_s') is not None)

    def cell(scene, act):
        return sum(r['scene'] == scene and r['observed_action'] == act for r in final)
    dev = {t['tag']: t for t in json.loads((RES / 'devset_summary.json').read_text())}
    d05 = lambda tag: next(r for r in dev[tag]['rows'] if r['tau'] == 0.5)
    acc = lambda tag: d05(tag)['allow_correct'] + d05(tag)['deny_correct']
    G, R, W = (60, 200, 120), (240, 80, 80), (236, 241, 248)
    m_runs = {k: json.loads((ROOT / 'outputs/runs' / v / 'mission.json').read_text(encoding='utf8'))
              for k, v in (('nominal', a.nominal), ('swapped', a.swapped), ('empty', a.empty))}
    item_ja = {'water': '飲料水', 'medicine': '医療物資'}
    n_item = item_ja[m_runs['nominal']['intent']['item']]
    s_item = item_ja[m_runs['swapped']['intent']['item']]
    e_item = item_ja[m_runs['empty']['intent']['item']]
    plan = {'parts': [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'image': 'docs/figures/hero_gazebo.png',
         'sub': '現地で「目で確かめてから」届ける災害物資ロボット',
         'body': ['ROS 2 Jazzy × Gazebo Harmonic × ローカルVLM（Qwen2.5-VL-3B / Tesla V100）',
                  '映像はすべて Gazebo の実レンダリング（俯瞰カメラ＋ロボット搭載カメラ）。',
                  '※ 走行区間は2〜3倍速、AI判断の区間は等速。速度は常に画面左上に表示します。']},
        {'kind': 'card', 'seconds': 9, 'title': 'なぜ「確かめる」のか',
         'sub': '災害時は、在庫表と棚の現物が食い違う',
         'body': ['「水があるはずの棚に救急箱がある」「棚が空」——指示どおり機械的に運ぶロボットは、誤った物資を自信満々に届けてしまう。',
                  'RescueMind は物資拠点で止まり、搭載カメラの画像をローカルVLMで確認。依頼どおりと高い確信で一致したときだけ避難所へ向かい、違えばその場で停止して人に委ねる。']},
        {'kind': 'card', 'seconds': 9, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
         'image': 'docs/figures/architecture.png', 'layout': 'image',
         'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']},
        {'kind': 'mission', 'index': 1, 'scene': 'nominal', 'run_dir': f'outputs/runs/{a.nominal}', 'fast': 2.0,
         'captions': {'go': f'指示「{m_runs["nominal"]["instruction"]}」を理解し、{n_item}の物資拠点へ自律移動します。',
                      'check': '到着したらカメラを棚に向けて静止を確認し、新しい画像をローカルVLMに2つの質問で確認させます。',
                      'after': f'2問とも「{n_item}」が最大かつ確率0.50以上で一致 → 許可。避難所Bへ向かいます（オレンジ線＝Gazebo真値の軌跡）。'}},
        {'kind': 'mission', 'index': 2, 'scene': 'swapped', 'run_dir': f'outputs/runs/{a.swapped}', 'fast': 3.0,
         'captions': {'go': f'次は在庫情報と現物が食い違うケース。同じく「{s_item}」を依頼します。',
                      'check': '拠点には依頼と違う物資が置かれています。VLMは何を見たと答えるか？',
                      'after': f'VLMは別の物資と判定 → 拒否。ロボットは避難所へ向かわず、その場で停止を保持します。'}},
        {'kind': 'mission', 'index': 3, 'scene': 'empty', 'run_dir': f'outputs/runs/{a.empty}', 'fast': 3.0,
         'captions': {'go': f'最後は欠品。「{e_item}」を依頼しますが、棚は空です。',
                      'check': '何もない棚を見て、物資を「幻覚」せずに済むか？',
                      'after': '「なし/不明」が最大 → 拒否して停止。誤った出発をしないことが最優先です。'}},
        {'kind': 'card', 'seconds': 8, 'title': 'VLMの使い方を変えて精度 37/48 → 48/48',
         'sub': '開発用画像48枚（視点をランダム化）での比較',
         'image': 'docs/figures/devset_ablation.png', 'layout': 'image',
         'body': [f'引継ぎ版の自由生成JSON：解析不能 {dev["qwen3b_json_baseline"]["parse_or_http_errors"]}回、空棚で「水」と幻覚  →  選択肢文字の確率を読む方式：{acc("qwen3b_scored")}/48・解析不能0',
                  '閾値0.50はこの開発セットだけで決め、評価前に事前登録（評価は別の30試行）']},
        {'kind': 'table', 'seconds': 12, 'title': f'事前登録30試行：VLM判断 {dec_ok}/{len(dec)}・誤許可 {fa}件',
         'sub': f'毎試行 Gazebo・ROS・VLM を新規起動。Gazebo真値・ROS bag による独立監査まで合格 {correct}/{len(final)}',
         'header': ['シーン（期待）', '許可→到着', '拒否→停止', '拒否(証拠不足)', '失敗'],
         'rows': [['正常配置（許可）', [str(cell('nominal', 'ALLOW')), G], cell('nominal', 'DENY'), cell('nominal', 'DENY_UNVERIFIED'), cell('nominal', 'FAILED')],
                  ['取り違え（拒否）', [str(cell('swapped', 'ALLOW')), R if cell('swapped', 'ALLOW') else W], [str(cell('swapped', 'DENY')), G], cell('swapped', 'DENY_UNVERIFIED'), cell('swapped', 'FAILED')],
                  ['欠品（拒否）', [str(cell('empty', 'ALLOW')), R if cell('empty', 'ALLOW') else W], [str(cell('empty', 'DENY')), G], cell('empty', 'DENY_UNVERIFIED'), cell('empty', 'FAILED')]],
         'notes': [f'VLM判断の遅延 中央値 {lat[len(lat)//2]:.2f} 秒（V100・FP16・VRAM約8GB）。',
                   '監査不合格2件：①拒否は正しいが停止証拠の時刻整合が3ms差で不合格（修正済）②許可・走行したが車輪オドメトリ誤差0.27mが上限0.25mを超過。',
                   '注意：3シーン×5反復であり30個の独立シーンではない。物資の把持・運搬は行わない。']},
        {'kind': 'card', 'seconds': 10, 'title': '動かして初めて分かったこと',
         'sub': '引継ぎ時点のコードは単体テスト506件に合格していたが、実機シミュレーションは未実行だった',
         'image': 'docs/figures/wheel_axis_regression.png',
         'body': ['車輪軸の定義誤り：オドメトリでは前進、実際は横滑り＋傾斜 → Gazebo真値で監査する仕組みを追加',
                  'Best Effort QoSで画像が102枚中10枚しか届かない → Reliableに統一',
                  'LiDARが自機のマストを障害物と誤検出 → 可視性マスクで除外', '全13件を docs/FINDINGS.md に記録']},
        {'kind': 'card', 'seconds': 7, 'title': 'RescueMind', 'sub': a.repo_url, 'image': 'docs/figures/hero_gazebo.png',
         'body': ['AIが間違えるとき、ロボットは動かない。それを物理真値で検証できる。',
                  'コード・事前登録・全試行の証拠・再現用Dockerを公開しています。']},
    ]}
    out = ROOT / 'docs/video_plan.json'
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(out)


if __name__ == '__main__':
    main()
