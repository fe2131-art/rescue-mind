#!/usr/bin/env python3
"""Site calibration of the hazard threshold tau_h on photographs taken where the robot will work (docs/DEPLOYMENT.md, section 3).

It applies the rule of study P2 (scripts/p2_calibration.py: the largest tau on the grid whose recall on the calibration half is >= 0.95;
wording with the lower calibration false-alarm rate; accepted only if the held-out half has recall >= 0.90 and false alarms <= 0.20) to
your own photographs, plus the PAC bound of study K (scripts/k_conformal.py) as a conservative reference.  It writes nothing into the repository.

  <photos>/none/*.jpg|png     no fire, no smoke (the normal site: lights, shelves, steam, dust, reflections ...)
  <photos>/hazard/*.jpg|png   fire or smoke clearly visible (a training fire source, a smoke machine, public photographs)

  python3 scripts/site_calibration.py --photos DIR --score --wording h36 [--port 8765]   # server: --prompt-set v35 --hazard-views tiles --hazard-prompt h36
  python3 scripts/site_calibration.py --photos DIR --score --wording h35                  # restart the server with --hazard-prompt h35 first
  python3 scripts/site_calibration.py --photos DIR --analyse                              # -> DIR/site_calibration.json, exit 2 if not accepted
  python3 scripts/site_calibration.py --selftest                                          # the rule on synthetic scores (no GPU, no photographs)

At least 100 photographs per class are needed (each half of the split needs 50).  The split is by the hash of the file name, so it is the same
every time and a photograph is never in both halves.  Only the scoring step needs the GPU server.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import p2_calibration as p2  # noqa: E402

MIN_PER_CLASS = 100
EXT = {'.jpg', '.jpeg', '.png'}
ALPHA, DELTA = 0.05, 0.10      # study K: miss rate <= alpha with probability >= 1 - delta


def scores_file(photos: Path, wording: str) -> Path:
    return photos / f'site_scores_{wording}.jsonl'


def list_photos(photos: Path):
    out = []
    for cls, cat in (('none', 'none'), ('hazard', 'smoke')):          # category names follow p2_calibration (only none / not-none matter)
        for f in sorted((photos / cls).glob('*')):
            if f.suffix.lower() in EXT and f.is_file():
                out.append({'file': f'{cls}/{f.name}', 'category': cat})
    return out


def split(recs):
    """Deterministic, balanced per class: sort by sha256 of the file name, even ranks -> calibration, odd ranks -> test."""
    cal, test = [], []
    for cat in ('none', 'smoke'):
        rs = sorted((r for r in recs if r['category'] == cat), key=lambda r: hashlib.sha256(r['file'].encode()).hexdigest())
        cal += rs[0::2]
        test += rs[1::2]
    return cal, test


def tau_pac(scores, alpha=ALPHA, delta=DELTA):
    """Study K: the k-th smallest hazard score of the calibration photographs with the largest k such that P(miss rate <= alpha) >= 1 - delta."""
    from scipy.stats import beta
    n = len(scores)
    ks = [k for k in range(1, n + 1) if beta.cdf(alpha, k, n + 1 - k) >= 1 - delta]
    return (sorted(scores)[max(ks) - 1], max(ks)) if ks else (0.0, 0)


def score(photos: Path, wording: str, port: int):
    from rescuemind.local_vision import _client_call
    out = scores_file(photos, wording)
    done = {json.loads(x)['file'] for x in out.read_text().splitlines()} if out.is_file() else set()
    todo = [r for r in list_photos(photos) if r['file'] not in done]
    for r in todo:
        resp = _client_call(f'http://127.0.0.1:{port}/v1/classify', p2.MODEL, (photos / r['file']).read_bytes(), 1, timeout=180)
        sc = resp.get('scores') or {}
        if sc.get('hazard_prompt') != wording or sc.get('hazard_views') != 'tiles':
            sys.exit(f'server is not configured as {wording} + tiles: {sc}')
        with out.open('a') as f:
            f.write(json.dumps({**r, 'wording': wording, 'hazard_prob': sc.get('hazard_prob')}) + '\n')
    print(f'scored {len(todo)} photographs to {out}')


def decide(by_wording: dict) -> dict:
    """by_wording: {wording: [records with file, category, hazard_prob]}.  Pure function (tested on synthetic scores)."""
    res = {'rule': 'P2: largest grid tau with calibration recall >= 0.95; accept if held-out recall >= 0.90 and false alarms <= 0.20',
           'min_per_class': MIN_PER_CLASS, 'grid': p2.GRID, 'wordings': {}}
    cal_by = {}
    for w, recs in by_wording.items():
        n_h = sum(r['category'] != 'none' for r in recs)
        n_n = sum(r['category'] == 'none' for r in recs)
        if n_h < MIN_PER_CLASS or n_n < MIN_PER_CLASS:
            res['wordings'][w] = {'status': 'too_few_photographs', 'hazard': n_h, 'none': n_n}
            continue
        cal, test = split(recs)
        cal_by[w] = cal
        res['wordings'][w] = {'status': 'scored', 'n_cal': len(cal), 'n_test': len(test), 'test': test}
    if not cal_by:
        res.update(chosen=None, accepted=False, reason='too few photographs (or no scores) for every wording')
        return res
    chosen, info = p2.choose_wording(cal_by, order=tuple(cal_by))
    for w, i in info.items():
        res['wordings'][w]['calibration'] = i
        cal_h = [p2.prob(r) for r in cal_by[w] if r['category'] != 'none']
        res['wordings'][w]['pac_tau_alpha_0.05'] = dict(zip(('tau', 'k'), tau_pac(cal_h)))
        test = res['wordings'][w].pop('test')
        if i['tau'] is not None:
            res['wordings'][w]['test_at_tau'] = p2.endpoint(test, i['tau'])
        res['wordings'][w]['test_at_tau_0.05'] = p2.endpoint(test, p2.FROZEN_TAU)
    res['chosen'] = chosen
    if chosen is None:
        res.update(accepted=False, reason='no tau on the grid reaches calibration recall >= 0.95: keep 0.05 and expect many false alarms, or take better photographs')
        return res
    ep = res['wordings'][chosen]['test_at_tau']
    ok = p2.claim(ep['recall']['rate'], ep['false_alarm']['rate'])
    res.update(accepted=ok, tau=info[chosen]['tau'],
               reason='accepted' if ok else f"held-out recall {ep['recall']['rate']:.3f} (need >= 0.90) / false alarms {ep['false_alarm']['rate']:.3f} (need <= 0.20): not accepted")
    return res


def analyse(photos: Path):
    by = {}
    for w in p2.WORDINGS:
        f = scores_file(photos, w)
        if f.is_file():
            by[w] = [r for r in (json.loads(x) for x in f.read_text().splitlines() if x.strip()) if r.get('hazard_prob') is not None]
    res = decide(by)
    (photos / 'site_calibration.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'grid'}, indent=1))
    if res['accepted']:
        t, w = res['tau'], res['chosen']
        print(f'\nACCEPTED: use the wording {w} and tau_h = {t}:\n'
              f'  local_vlm_server.py ... --hazard-prompt {w} --hazard-views tiles --hazard-threshold {t}\n'
              f'  mission node:        --expected-hazard-threshold {t}\n'
              f'  delivery interlock:  --hazard-threshold {t}   (a record under another value is refused)\n'
              f'  (with scripts/v32_orchestrate.py: --hazard-prompt {w} --hazard-threshold {t} sets all three)')
    else:
        print('\nNOT ACCEPTED: ' + res['reason'])
    return 0 if res['accepted'] else 2


def selftest() -> int:
    """`--selftest`: the decision rule on synthetic scores (no model, no photographs).  Kept here, not in tests/, on purpose: the
    documents print the number of test functions of tests/, and every change of it must be propagated to them."""
    import random
    import unittest

    def recs(hazard, none):
        return ([{'file': f'hazard/a{i}.jpg', 'category': 'smoke', 'hazard_prob': x} for i, x in enumerate(hazard)] +
                [{'file': f'none/a{i}.jpg', 'category': 'none', 'hazard_prob': x} for i, x in enumerate(none)])

    class Case(unittest.TestCase):
        def test_split_is_deterministic_disjoint_and_balanced(self):
            r = recs([0.5] * 120, [0.1] * 101)
            cal, test = split(r)
            self.assertEqual(cal, split(list(reversed(r)))[0])
            self.assertFalse({x['file'] for x in cal} & {x['file'] for x in test})
            self.assertEqual(len(cal) + len(test), 221)
            self.assertEqual(sum(x['category'] == 'smoke' for x in cal), 60)

        def test_too_few_photographs_is_not_accepted(self):
            res = decide({'h36': recs([0.9] * 99, [0.0] * 200)})
            self.assertFalse(res['accepted'])
            self.assertEqual(res['wordings']['h36']['status'], 'too_few_photographs')

        def test_separable_scores_are_accepted_at_the_largest_qualifying_tau(self):
            rng = random.Random(1)
            res = decide({'h36': recs([rng.uniform(0.4, 0.99) for _ in range(150)], [rng.uniform(0.0, 0.04) for _ in range(150)])})
            self.assertTrue(res['accepted'], res['reason'])
            self.assertEqual(res['tau'], 0.4)           # all hazard scores >= 0.4: recall 1.0 up to the grid value 0.4
            self.assertEqual(res['wordings']['h36']['test_at_tau']['false_alarm']['k'], 0)

        def test_overlapping_scores_are_not_accepted(self):
            rng = random.Random(2)
            res = decide({'h36': recs([rng.uniform(0.0, 0.2) for _ in range(150)], [rng.uniform(0.0, 0.2) for _ in range(150)])})
            self.assertFalse(res['accepted'])

        def test_no_feasible_tau(self):
            res = decide({'h36': recs([0.0] * 150, [0.0] * 150)})
            self.assertFalse(res['accepted'])
            self.assertIsNone(res['chosen'])

        def test_wording_with_fewer_false_alarms_wins(self):
            rng = random.Random(3)
            hz = [rng.uniform(0.5, 0.99) for _ in range(150)]
            res = decide({'h36': recs(hz, [rng.uniform(0.0, 0.6) for _ in range(150)]), 'h35': recs(hz, [rng.uniform(0.0, 0.05) for _ in range(150)])})
            self.assertEqual(res['chosen'], 'h35')

        def test_pac_threshold_is_a_calibration_score(self):
            s = [i / 100 for i in range(1, 101)]
            tau, k = tau_pac(s)
            self.assertIn(tau, s)
            self.assertGreaterEqual(k, 1)

    r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Case))
    return 0 if r.wasSuccessful() else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--photos', type=Path)
    ap.add_argument('--selftest', action='store_true', help='check the decision rule on synthetic scores')
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--analyse', action='store_true')
    ap.add_argument('--wording', choices=p2.WORDINGS)
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.photos:
        ap.error('--photos is required')
    photos = a.photos.expanduser()
    if a.score:
        if not a.wording:
            ap.error('--score needs --wording')
        score(photos, a.wording, a.port)
    if a.analyse:
        sys.exit(analyse(photos))


if __name__ == '__main__':
    main()
