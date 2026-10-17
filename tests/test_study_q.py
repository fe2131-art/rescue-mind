"""Study Q: sampling determinism, label logic, licence filter and the analysis on synthetic scores (no network, no model)."""
import json
import unittest

from scripts import q_analysis as qa
from scripts import q_eval as qe
from scripts import q_fetch as qf


def listing(n, cat, base=0, lic='CC BY-SA 4.0', **kw):
    return [dict({'pageid': base + i, 'title': f'File:{cat} {i}.jpg', 'page_url': 'u', 'thumb_url': 't', 'mime': 'image/jpeg',
                  'width': 1200, 'height': 800, 'licence': lic, 'licence_url': 'l', 'artist': f'a{i}'}, **kw) for i in range(n)]


def candidates(per=40):
    out = []
    for cls, typ in (('water', 'bottled_water'), ('medicine', 'first_aid_kits'), ('neither', 'toolbox'), ('neither', 'soda_bottle')):
        for i in range(per):
            out.append({'id': len(out) + 1, 'class': cls, 'type': typ, 'artist': f'{typ}{i % 20}', 'file': f'{len(out) + 1}.jpg'})
    return out


class Fetch(unittest.TestCase):
    def test_licence_policy(self):
        for ok in ('CC0', 'CC BY 4.0', 'CC BY-SA 3.0', 'CC BY 2.0', 'CC BY-SA 3.0 de', 'Public domain', 'CC BY-SA 4.0'):
            self.assertTrue(qf.licence_ok(ok), ok)
        for bad in ('CC BY-NC 2.0', 'CC BY-ND 4.0', 'CC BY-NC-SA 3.0', 'GFDL', 'Fair use', '', None, 'Copyrighted free use'):
            self.assertFalse(qf.licence_ok(bad), bad)

    def test_usable_filters(self):
        r = listing(1, 'x')[0]
        self.assertTrue(qf.usable(r))
        self.assertFalse(qf.usable({**r, 'mime': 'image/svg+xml'}))
        self.assertFalse(qf.usable({**r, 'width': 300}))
        self.assertFalse(qf.usable({**r, 'width': 3000, 'height': 500}))
        self.assertFalse(qf.usable({**r, 'title': 'File:Water bottle logo.jpg'}))
        self.assertFalse(qf.usable({**r, 'licence': 'CC BY-NC 4.0'}))

    def test_draw_is_deterministic_and_capped(self):
        src = [('water', 'a', 'A', 5), ('medicine', 'b', 'B', 7)]
        ls = {'A': listing(30, 'A'), 'B': listing(30, 'B', base=1000)}
        d1, d2 = qf.draw(ls, src), qf.draw(ls, src)
        self.assertEqual(json.dumps(d1), json.dumps(d2))
        self.assertEqual([sum(r['class'] == c for r in d1) for c in ('water', 'medicine')], [5, 7])
        self.assertNotEqual([r['id'] for r in d1], [r['id'] for r in qf.draw(ls, src, seed='other')])

    def test_class_clash_and_duplicates(self):
        src = [('water', 'a', 'A', 50), ('medicine', 'b', 'B', 50), ('water', 'c', 'C', 50)]
        shared = listing(3, 'S', base=500)
        ls = {'A': listing(5, 'A') + shared, 'B': listing(5, 'B', base=100) + shared[:1], 'C': listing(4, 'C', base=900) + shared[1:]}
        got = qf.draw(ls, src)
        ids = [r['id'] for r in got]
        self.assertNotIn(500, ids)                       # in a water and a medicine category: dropped everywhere
        self.assertEqual(ids.count(501), 1)              # twice in water: kept once, by the first source
        self.assertEqual([r['type'] for r in got if r['id'] == 501], ['a'])


class Sampling(unittest.TestCase):
    def test_exclusions_are_removed_and_counts_capped(self):
        cand = candidates()
        excl = {1: 'x', 2: 'y'}
        fin = qe.final_sample(cand, excl, target=15, max_per_artist=8)
        ids = {r['id'] for r in fin}
        self.assertFalse(ids & set(excl))
        for c in ('water', 'medicine', 'neither'):
            self.assertEqual(sum(r['class'] == c for r in fin), 15)

    def test_deterministic_and_seeded(self):
        cand = candidates()
        a = qe.final_sample(cand, {}, target=15)
        self.assertEqual(a, qe.final_sample(cand, {}, target=15))
        self.assertNotEqual([r['id'] for r in a], [r['id'] for r in qe.final_sample(cand, {}, target=15, seed='x')])

    def test_artist_cap(self):
        cand = [{'id': i, 'class': 'water', 'type': 't', 'artist': 'same', 'file': 'f'} for i in range(30)]
        self.assertEqual(len(qe.final_sample(cand, {}, target=100, max_per_artist=8)), 8)

    def test_requests_and_labels(self):
        imgs = qe.assign_requests(qe.final_sample(candidates(), {}, target=20))
        by = lambda f: [r for r in imgs if f(r)]
        for c in ('water', 'medicine'):
            own = by(lambda r: r['class'] == c and r['requested'] == c)
            self.assertEqual(len(own), 10)                           # exactly half request their own supply
            self.assertTrue(all(r['expected'] == 'allow' and r['refusal_kind'] is None for r in own))
            other = by(lambda r: r['class'] == c and r['requested'] != c)
            self.assertTrue(all(r['expected'] == 'deny' and r['refusal_kind'] == 'wrong_supply' for r in other))
        nei = by(lambda r: r['class'] == 'neither')
        self.assertEqual({r['expected'] for r in nei}, {'deny'})
        self.assertEqual(sum(r['requested'] == 'water' for r in nei), 10)
        self.assertTrue(all(r['refusal_kind'].startswith('neither:') for r in nei))
        self.assertEqual(imgs, qe.assign_requests(qe.final_sample(candidates(), {}, target=20)))

    def test_exclusion_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'e.json'
            self.assertEqual(qe.load_exclusions(p), {})
            p.write_text(json.dumps({'excluded': [{'id': 7, 'reason': 'r'}]}))
            self.assertEqual(qe.load_exclusions(p), {7: 'r'})


def rec(i, cls, requested, p1, p2, typ='toolbox'):
    """p1/p2: closed-set probability dicts of the two passes."""
    return {'id': i, 'class': cls, 'type': typ, 'requested': requested, 'expected': 'allow' if cls == requested else 'deny',
            'refusal_kind': None if cls == requested else ('wrong_supply' if cls != 'neither' else 'neither:' + typ),
            'passes': {'1': {'supply': 'x', 'scores': {'supply_probs': p1}}, '2': {'supply': 'x', 'scores': {'supply_probs': p2}}}}


def P(w=0.0, m=0.0, o=0.0):
    return {'water': w, 'medicine': m, 'other': o}


class Analysis(unittest.TestCase):
    def test_decision_rule(self):
        good = rec(1, 'water', 'water', P(w=0.9, o=0.1), P(w=0.8, o=0.2))
        self.assertTrue(qa.vlm_approves(good))
        self.assertFalse(qa.vlm_approves(rec(2, 'water', 'water', P(w=0.9, o=0.1), P(w=0.45, o=0.55))))        # second pass below 0.5 / not arg-max
        self.assertFalse(qa.vlm_approves(rec(3, 'water', 'water', P(w=0.49, m=0.48, o=0.03), P(w=0.9, o=0.1))))  # arg-max but < tau_s
        self.assertFalse(qa.vlm_approves(rec(4, 'medicine', 'water', P(m=0.9, w=0.1), P(m=0.9, w=0.1))))      # wrong supply
        bad = rec(6, 'water', 'water', P(w=0.9), P(w=0.9))
        bad['passes']['2'] = {'error': 'boom'}
        self.assertFalse(qa.vlm_approves(bad))                                                                  # an error is a refusal

    def test_zero_shot_rule(self):
        self.assertTrue(qa.zs_approves(P(w=0.5, m=0.3, o=0.2), 'water'))
        self.assertFalse(qa.zs_approves(P(w=0.3, m=0.4, o=0.3), 'water'))
        self.assertFalse(qa.zs_approves(P(w=0.33, m=0.32, o=0.31), 'water'))                                   # arg-max but below 0.34

    def synthetic(self, fa_neither=0, ca=130):
        recs = []
        i = 0
        for cls in ('water', 'medicine'):                               # 75 own request, 75 other request
            for k in range(150):
                i += 1
                req = cls if k < 75 else ('medicine' if cls == 'water' else 'water')
                if req == cls:   # approve the first `ca/2` of them
                    ok = k < ca // 2
                    pr = P(**{'w' if cls == 'water' else 'm': 0.9, 'o': 0.1}) if ok else P(o=0.9, w=0.05, m=0.05)
                else:
                    pr = P(o=0.9, w=0.05, m=0.05)
                recs.append(rec(i, cls, req, pr, pr))
        for k in range(150):
            i += 1
            typ = 'toolbox' if k < 75 else 'soda'
            req = 'water' if k % 2 else 'medicine'
            pr = P(**{'w' if req == 'water' else 'm': 0.9, 'o': 0.1}) if k < fa_neither else P(o=0.9, w=0.05, m=0.05)
            recs.append(rec(i, 'neither', req, pr, pr, typ=typ))
        return recs

    def test_counts_and_claim_supported(self):
        out = qa.analyse(self.synthetic(fa_neither=0, ca=130))
        c = out['qwen9b_v35']
        self.assertEqual((c['n_deny'], c['n_allow']), (300, 150))
        self.assertEqual((c['FA'], c['CA']), (0, 130))
        self.assertLessEqual(c['FA_ci'][1], 0.05)
        self.assertTrue(c['claim']['supply_check_transfers'])
        self.assertEqual(out['breakdown']['false_approvals']['neither_all']['n'], 150)

    def test_claim_fails_on_false_approvals_and_on_availability(self):
        c = qa.analyse(self.synthetic(fa_neither=20, ca=130))['qwen9b_v35']
        self.assertEqual(c['FA'], 20)
        self.assertFalse(c['claim']['supply_check_transfers'])
        self.assertIn('false approvals', c['claim']['verdict'])
        c = qa.analyse(self.synthetic(fa_neither=0, ca=100))['qwen9b_v35']          # 100/150 = 0.667 < 0.70
        self.assertFalse(c['claim']['availability_CA_ge_0.70'])
        self.assertTrue(c['claim']['safety_FA_upper_bound_le_0.05'])

    def test_boundary_of_safety_criterion(self):
        # 300 must-refuse images: the largest number of false approvals that still meets the 5% upper-bound criterion
        ks = [k for k in range(0, 30) if qa.wilson(k, 300)[1] <= 0.05]
        self.assertEqual(max(ks), 7)                                              # 7/300 = 2.3% (upper 0.0474); 8/300 has upper 0.0517

    def test_breakdown_alert_and_paired(self):
        recs = self.synthetic(fa_neither=5)
        out = qa.analyse(recs)
        self.assertEqual(out['breakdown']['false_approvals']['neither:toolbox']['k'], 5)
        self.assertIn('neither:toolbox', out['breakdown']['types_at_or_above_alert'])
        zs = {str(r['id']): P(w=0.34, m=0.33, o=0.33) for r in recs}               # baseline approves every water request
        out = qa.analyse(recs, {'siglip': zs})
        s = out['siglip']
        self.assertEqual(s['counts']['CA'] + s['counts']['FA'], sum(r['requested'] == 'water' for r in recs))
        self.assertGreater(s['counts']['FA'], out['qwen9b_v35']['FA'])
        self.assertLess(s['mcnemar_vs_qwen']['deny']['p'], 0.05)
        self.assertIn('safer', s['outcome'])

    def test_sensitivity_monotone(self):
        out = qa.analyse(self.synthetic(fa_neither=5))
        t = out['tau_s_sensitivity']
        self.assertGreaterEqual(t['0.5']['FA'], t['0.9']['FA'])
        self.assertGreaterEqual(t['0.5']['CA'], t['0.9']['CA'])


if __name__ == '__main__':
    unittest.main()
