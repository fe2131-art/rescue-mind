#!/usr/bin/env python3
"""Study Z: non-generative zero-shot baselines (SigLIP, CLIP), exactly as pre-registered in
experiments/PREREGISTRATION_Z.md.

  python3 scripts/zeroshot_baseline.py          # scores -> thresholds (dev only) -> evaluation

Outputs (experiments/results/): z_scores_{siglip,clip}.json, z_thresholds.json, z_summary.json,
and docs/paper/tab_z.tex.  Scores are cached; delete the cache file to recompute.
Order of operations: (1) raw probabilities for all images, (2) thresholds selected from DEVELOPMENT rows only
(select_thresholds never receives T1/T2 rows) and written + printed, (3) T1/T2 evaluation reads z_thresholds.json.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from i13_select import expected, q_allows  # noqa: E402  (dev expectation + our decision rule)
from t1_analysis import wilson, mcnemar_exact  # noqa: E402

EXP = ROOT / 'experiments'
RES = EXP / 'results'

MODELS = {'siglip': 'google/siglip-so400m-patch14-384', 'clip': 'openai/clip-vit-large-patch14'}
DEV_SETS = {'v1': 'vlm_devset', 'v2': 'vlm_devset_v2', 'dh': 'vlm_devset_hazard', 'dh2': 'vlm_devset_hazard2'}
TEST_SETS = {'t1': 'vlm_testset_t1', 't2': 'vlm_testset_t2'}
OURS = {'t1': 'devset_t1_qwen35_9b.json', 't2': 'devset_t2_i11_h36_tiles.json'}
OURS_TAU_H = 0.05

# ---- prompts: fixed before any scoring (PREREGISTRATION_Z.md) ----
SUPPLY_KEYS = ('water', 'medicine', 'other')
SUPPLY_PROMPTS = ('a pack of plastic water bottles on a grey platform',
                  'a white first-aid kit with a red cross on a grey platform',
                  'an empty grey platform or some other object')
HAZARD_PROMPTS = ('fire, flames or smoke', 'no fire and no smoke')   # index 0 = hazard

TAU_S_GRID = [round(0.34 + 0.06 * i, 2) for i in range(11)]    # 0.34, 0.40, ..., 0.94
TAU_H_GRID = [round(0.05 * i, 2) for i in range(1, 20)]        # 0.05, 0.10, ..., 0.95


# ---------------------------------------------------------------- decision + threshold selection (no model)
def approves(station, supply_probs, hazard_max, tau_s, tau_h):
    """Approve iff arg-max supply is the requested one, its probability >= tau_s and hazard < tau_h."""
    best = max(supply_probs, key=supply_probs.get)
    return best == station and supply_probs[station] >= tau_s and hazard_max < tau_h


def select_thresholds(rows, tau_s_grid=TAU_S_GRID, tau_h_grid=TAU_H_GRID):
    """rows: dicts with expected ('allow'|'deny'), station, supply_probs, hazard_max (development rows only).
    Rule: fewest false approvals; among those the most correct approvals; ties -> lower tau_h.
    (The pre-registration does not order a residual tie in tau_s; the lower tau_s is taken, deterministically.)"""
    best = None
    for tau_h in tau_h_grid:
        for tau_s in tau_s_grid:
            fa = ca = 0
            for r in rows:
                a = approves(r['station'], r['supply_probs'], r['hazard_max'], tau_s, tau_h)
                if r['expected'] == 'deny':
                    fa += a
                else:
                    ca += a
            key = (fa, -ca, tau_h, tau_s)
            if best is None or key < best[0]:
                best = (key, {'tau_s': tau_s, 'tau_h': tau_h, 'dev_false_approvals': fa, 'dev_correct_approvals': ca})
    n_deny = sum(r['expected'] == 'deny' for r in rows)
    n_allow = sum(r['expected'] == 'allow' for r in rows)
    return {**best[1], 'dev_n_deny': n_deny, 'dev_n_allow': n_allow}


# ---------------------------------------------------------------- data
def read_labels(dirname):
    f = EXP / dirname / 'labels.jsonl'
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]


def all_images():
    """[(set_tag, directory, label_row)] for dev + T1 + T2."""
    out = []
    for tag, d in {**DEV_SETS, **TEST_SETS}.items():
        for r in read_labels(d):
            out.append((tag, d, r))
    return out


# ---------------------------------------------------------------- scoring (GPU)
def score_model(name, items, batch=4):
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    from scripts.local_vlm_server import ModelWorker   # source of the three crops (v3.6 'tiles' hazard views)
    mid = MODELS[name]
    proc = AutoProcessor.from_pretrained(mid)
    model = AutoModel.from_pretrained(mid, torch_dtype=torch.float16).cuda().eval()
    kw = {'padding': 'max_length', 'max_length': 64} if name == 'siglip' else {'padding': True}

    def text_logits(texts):
        t = proc(text=list(texts), return_tensors='pt', **kw)
        return t

    with torch.inference_mode():
        def encode_text(texts):
            t = text_logits(texts)
            t = {k: v.cuda() for k, v in t.items() if k in ('input_ids', 'attention_mask')}
            return model.get_text_features(**t)
        tf_supply = encode_text(SUPPLY_PROMPTS)
        tf_hazard = encode_text(HAZARD_PROMPTS)
        tf_supply = tf_supply / tf_supply.norm(dim=-1, keepdim=True)
        tf_hazard = tf_hazard / tf_hazard.norm(dim=-1, keepdim=True)
        scale = model.logit_scale.exp()
        bias = getattr(model, 'logit_bias', None)

        def logits(img_feats, tf):
            l = scale * img_feats @ tf.T
            return l + bias if bias is not None else l   # a constant bias does not change a softmax

        scores = {}
        for i, (tag, d, r) in enumerate(items):
            pic = Image.open(EXP / d / r['image']).convert('RGB')
            views = [pic] + ModelWorker._crops(pic)       # full, left 60%, right 60%, top 60% (enlarged to 640 px)
            px = proc(images=views, return_tensors='pt')['pixel_values'].cuda().half()
            f = model.get_image_features(pixel_values=px)
            f = f / f.norm(dim=-1, keepdim=True)
            sp = torch.softmax(logits(f[0:1], tf_supply).float(), -1)[0].tolist()
            hz = torch.softmax(logits(f, tf_hazard).float(), -1)[:, 0].tolist()
            scores[f'{tag}|{r["image"]}'] = {
                'supply_probs': {k: round(p, 6) for k, p in zip(SUPPLY_KEYS, sp)},
                'hazard_views': [round(h, 6) for h in hz],     # full, left, right, top
                'hazard_max': round(max(hz), 6)}
            if (i + 1) % 200 == 0:
                print(f'  {name}: {i + 1}/{len(items)}', flush=True)
    del model
    torch.cuda.empty_cache()
    return scores


def get_scores(name, items):
    f = RES / f'z_scores_{name}.json'
    if f.is_file():
        d = json.loads(f.read_text())
        if all(f'{t}|{r["image"]}' in d['scores'] for t, _, r in items):
            return d['scores']
    print(f'scoring {name} ({MODELS[name]}) on {len(items)} images', flush=True)
    scores = score_model(name, items)
    f.write_text(json.dumps({'model': MODELS[name], 'supply_prompts': SUPPLY_PROMPTS, 'hazard_prompts': HAZARD_PROMPTS,
                             'scores': scores}) + '\n')
    return scores


# ---------------------------------------------------------------- evaluation
def rows_for(scores, items, tags):
    rows = []
    for tag, d, r in items:
        if tag not in tags:
            continue
        e = expected(r) if tag in DEV_SETS else r['expected']
        if e == 'ambiguous':
            continue
        s = scores[f'{tag}|{r["image"]}']
        rows.append({'key': f'{tag}|{r["image"]}', 'expected': e, 'station': r['station'],
                     'supply_probs': s['supply_probs'], 'hazard_max': s['hazard_max']})
    return rows


def counts(approved, rows):
    fa = sum(approved[r['key']] for r in rows if r['expected'] == 'deny')
    ca = sum(approved[r['key']] for r in rows if r['expected'] == 'allow')
    nd = sum(r['expected'] == 'deny' for r in rows)
    na = sum(r['expected'] == 'allow' for r in rows)
    return {'FA': fa, 'n_deny': nd, 'FA_ci': wilson(fa, nd), 'CA': ca, 'n_allow': na, 'CA_ci': wilson(ca, na)}


def ours_decisions(tag, rows):
    recs = json.loads((RES / OURS[tag]).read_text())['records']
    by = {r['image']: r for r in recs}
    return {r['key']: bool(q_allows(by[r['key'].split('|', 1)[1]], OURS_TAU_H)) for r in rows}


def paired(rows, z_app, o_app):
    """Exact McNemar, ours vs baseline, on must-refuse (false approvals) and must-approve (correct approvals)."""
    out = {}
    for label, e in (('deny', 'deny'), ('allow', 'allow')):
        sel = [r['key'] for r in rows if r['expected'] == e]
        only_o = sum(o_app[k] and not z_app[k] for k in sel)
        only_z = sum(z_app[k] and not o_app[k] for k in sel)
        out[label] = {'ours_only_approved': only_o, 'baseline_only_approved': only_z,
                      'p': round(mcnemar_exact(only_o, only_z), 6)}
    return out


def claim_outcome(per_set):
    """Claim rule of the pre-registration, applied per test set and then over {T1, T2}.
    safer: ours has fewer FA with p<0.05 on T1 or T2, and ours' CA are not lower with p<0.05 (same set).
    more available: ours has more CA with p<0.05, and ours' FA are not higher with p<0.05 (same set)."""
    safer, avail = [], []
    for s, v in per_set.items():
        fa_o, fa_z, ca_o, ca_z = v['ours']['FA'], v['baseline']['FA'], v['ours']['CA'], v['baseline']['CA']
        pf, pc = v['mcnemar']['deny']['p'], v['mcnemar']['allow']['p']
        if fa_o < fa_z and pf < 0.05 and not (ca_o < ca_z and pc < 0.05):
            safer.append(s)
        if ca_o > ca_z and pc < 0.05 and not (fa_o > fa_z and pf < 0.05):
            avail.append(s)
    res = []
    if safer:
        res.append('The VLM check is safer than the zero-shot baseline (' + ', '.join(s.upper() for s in safer) + ')')
    if avail:
        res.append('The VLM check is more available than the zero-shot baseline (' + ', '.join(s.upper() for s in avail) + ')')
    return '; '.join(res) if res else 'no significant difference (counts reported)'


def pct(k, n):
    return f'{100 * k / n:.1f}' if n else '--'


def cell(c, key, nkey, cikey):
    lo, hi = c[cikey]
    return f'{c[key]}/{c[nkey]} ({pct(c[key], c[nkey])}\\%) [{100 * lo:.1f}, {100 * hi:.1f}]'


def write_table(summary):
    names = {'siglip': 'SigLIP (so400m, zero-shot)', 'clip': 'CLIP (ViT-L/14, zero-shot)'}
    lines = ['% generated by scripts/zeroshot_baseline.py', '\\begin{tabular}{lcccc}', '\\toprule',
             'System & T1 FA & T1 CA & T2 FA & T2 CA \\\\', '\\midrule']
    ours = {t: summary['models']['siglip'][t]['ours'] for t in ('t1', 't2')}
    lines.append('Ours (T1 v3.5, T2 v3.6) & ' + ' & '.join(
        cell(ours[t], k, n, ci) for t in ('t1', 't2') for k, n, ci in (('FA', 'n_deny', 'FA_ci'), ('CA', 'n_allow', 'CA_ci'))) + ' \\\\')
    for m in ('siglip', 'clip'):
        z = {t: summary['models'][m][t]['baseline'] for t in ('t1', 't2')}
        lines.append(names[m] + ' & ' + ' & '.join(
            cell(z[t], k, n, ci) for t in ('t1', 't2') for k, n, ci in (('FA', 'n_deny', 'FA_ci'), ('CA', 'n_allow', 'CA_ci'))) + ' \\\\')
    lines += ['\\bottomrule', '\\end{tabular}', '']
    (ROOT / 'docs/paper/tab_z.tex').write_text('\n'.join(lines))


def main():
    items = all_images()
    scores = {m: get_scores(m, items) for m in MODELS}

    # ---- threshold selection: DEVELOPMENT rows only ----
    thresholds = {}
    for m in MODELS:
        dev_rows = rows_for(scores[m], items, set(DEV_SETS))
        thresholds[m] = select_thresholds(dev_rows)
    (RES / 'z_thresholds.json').write_text(json.dumps(thresholds, indent=1) + '\n')
    print('THRESHOLDS (development only):')
    print(json.dumps(thresholds, indent=1), flush=True)

    # ---- evaluation on held-out T1/T2 (reads the written thresholds) ----
    thr = json.loads((RES / 'z_thresholds.json').read_text())
    summary = {'prereg': 'experiments/PREREGISTRATION_Z.md', 'thresholds': thr, 'models': {}}
    for m in MODELS:
        summary['models'][m] = {}
        for tag in TEST_SETS:
            rows = rows_for(scores[m], items, {tag})
            z_app = {r['key']: approves(r['station'], r['supply_probs'], r['hazard_max'], thr[m]['tau_s'], thr[m]['tau_h'])
                     for r in rows}
            o_app = ours_decisions(tag, rows)
            summary['models'][m][tag] = {'baseline': counts(z_app, rows), 'ours': counts(o_app, rows),
                                         'mcnemar': paired(rows, z_app, o_app)}
        summary['models'][m]['claim'] = claim_outcome({t: summary['models'][m][t] for t in TEST_SETS})
    (RES / 'z_summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    write_table(summary)
    for m in MODELS:
        for t in TEST_SETS:
            v = summary['models'][m][t]
            print(f"{m} {t}: baseline FA {v['baseline']['FA']}/{v['baseline']['n_deny']} CA {v['baseline']['CA']}/{v['baseline']['n_allow']} | "
                  f"ours FA {v['ours']['FA']} CA {v['ours']['CA']} | McNemar p deny {v['mcnemar']['deny']['p']} allow {v['mcnemar']['allow']['p']}")
        print(m, 'CLAIM:', summary['models'][m]['claim'])


if __name__ == '__main__':
    main()
