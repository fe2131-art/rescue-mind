#!/usr/bin/env python3
"""How much do the two permuted-option supply questions disagree? (I-119; POST HOC on the saved gate outputs of XD, JI and the T1 set; no new data.)

  python3 scripts/permutation_agreement.py     # -> experiments/results/permutation_agreement.json
The gate asks the supply question twice with differently worded, option-permuted prompts (pass 1: A water / B medicine / C other; pass 2: A other / B medicine / C water).  Reviewers of token-probability scoring
(option-letter and position bias, prompt-wording sensitivity) ask how often the two passes disagree and whether the disagreement is informative.  Per image: argmax agreement of the two passes, the absolute difference of
the probability of the true supply, and accuracy of each pass against the truth (images where the truth is water or medicine).  Descriptive, no claim.
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'


def probs(pass_):
    return ((pass_ or {}).get('scores') or {}).get('supply_probs')


def analyse(name, f):
    recs = json.loads((RES / f).read_text(encoding='utf8'))['records']
    n = agree = 0
    acc1 = acc2 = 0
    diffs = []
    for r in recs:
        truth = r.get('truth_supply') or r.get('station')
        p1, p2 = probs((r.get('passes') or {}).get('1')), probs((r.get('passes') or {}).get('2'))
        if not p1 or not p2 or truth not in ('water', 'medicine'):
            continue
        a1, a2 = max(p1, key=p1.get), max(p2, key=p2.get)
        n += 1
        agree += a1 == a2
        acc1 += a1 == truth
        acc2 += a2 == truth
        diffs.append(abs(p1.get(truth, 0.0) - p2.get(truth, 0.0)))
    return {'file': f, 'n_images': n, 'argmax_agree': agree, 'argmax_disagree': n - agree, 'accuracy_pass1': round(acc1 / n, 4) if n else None, 'accuracy_pass2': round(acc2 / n, 4) if n else None,
            'median_abs_diff_p_true': round(statistics.median(diffs), 4) if diffs else None, 'share_abs_diff_over_0.1': round(sum(d > 0.1 for d in diffs) / n, 4) if n else None}


def main():
    out = {'post_hoc': True}
    for name, f in (('XD', 'devset_xd_h36_tiles.json'), ('JI', 'devset_ji_h36_tiles.json'), ('T1', 'devset_t1_qwen35_9b.json')):
        try:
            out[name] = analyse(name, f)
        except Exception as e:
            out[name] = {'error': f'{type(e).__name__}: {e}'[:200]}
    (RES / 'permutation_agreement.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
