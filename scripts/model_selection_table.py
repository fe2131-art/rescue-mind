#!/usr/bin/env python3
"""I-08: one table for the model decision, built only from saved evaluation files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
MODELS = [('Qwen2.5-VL-3B', 'qwen25vl3b', '2025-01', 'Qwen Research（研究用途）'),
          ('Qwen3-VL-8B', 'qwen3vl8b', '2025-10', 'Apache-2.0'),
          ('Qwen3.5-4B', 'qwen35_4b', '2026-02', 'Apache-2.0'),
          ('Qwen3.5-9B', 'qwen35_9b', '2026-02', 'Apache-2.0')]


def load(name):
    f = RES / name
    return json.loads(f.read_text()) if f.is_file() else None


def main():
    rob = load('i05_robustness_summary.json') or {}
    rows = []
    for label, tag, date, lic in MODELS:
        r = {'model': label, 'released': date, 'license': lic}
        for ps in ('v34', 'v35'):
            k = f'{label}_{ps}' if not (label == 'Qwen2.5-VL-3B' and ps == 'v34') else 'M1_v34'
            if k in rob:
                g = next(x for x in rob[k]['grid'] if x['tau_s'] == 0.5 and x['tau_h'] == 0.5)
                r[f'vision_{ps}'] = f"{g['correct']}/{g['n']} (FA {g['false_approval']}, FD {g['false_denial']})"
                r[f'margin_{ps}'] = (rob[k]['margins']['positive_min_p_requested'], rob[k]['margins']['negative_max_p_requested'])
                r[f'latency_{ps}'] = rob[k].get('mean_latency_per_pass_s')
        e = load(f'explain_e0_{tag}.json') or (load('explain_e0.json') if tag == 'qwen25vl3b' else None)
        if e:
            r['explain'] = f"{e['summary']['correct']}/{e['summary']['n']}"
        for ip in ('i34', 'i35'):
            d = load(f'intent_hybrid_{ip}_{tag}_dev_v35.json')
            if d:
                r[f'intent_dev_{ip}'] = f"{d['summary']['correct']}/{d['summary']['n']} (unsafe {d['summary']['unsafe_accepts']})"
        v = RES / f'vram_{tag}.txt'
        if v.is_file():
            r['vram'] = v.read_text().strip()
        rows.append(r)
    (RES / 'i08_model_selection.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
