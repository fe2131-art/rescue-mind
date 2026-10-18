"""I-24 study B: protocol generator, the run_campaign advice_credit trial field and b_analysis on synthetic mission.json
fixtures.  Nothing here needs ROS, Gazebo or a GPU: a stand-in robot plans with the real advice/credit code, writes the
mission.json a run would write and settles the ledger with the orchestrator's own settle_credit."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import advice_credit as ac  # noqa: E402
from rescuemind.advice_llm import plan_for_mission  # noqa: E402
from scripts import make_protocol_b as mpb  # noqa: E402
from scripts import b_analysis as ba  # noqa: E402
from scripts import run_campaign as rc  # noqa: E402
from scripts import v32_orchestrate as orch  # noqa: E402

OTHER = {'water': 'medicine', 'medicine': 'water'}


def cp(exp, seen, allow, reason='ok'):
    return {'decision': {'expected': exp, 'first_supply': seen, 'second_supply': seen, 'allow': allow, 'reason': reason}}


def simulate(proto, tmp: Path, *, ignore_credit=False, wrong_station_unsafe=None, drop=(), no_json=(), time_per_visit=40.0):
    """A stand-in robot over the whole protocol.  Returns the ledger rows.  Files live under `tmp`."""
    runs, rows = tmp / 'runs', []
    runs.mkdir(exist_ok=True)
    for t in sorted(proto['trials'], key=lambda t: t['order']):
        if t['id'] in drop:
            continue
        item = t['expected']
        holder = item if t['scene'] == 'nominal' else OTHER[item]
        credit = (tmp / t['advice_credit']['file']) if (t.get('advice_credit') and not ignore_credit) else None
        if credit is not None:
            if t['advice_credit']['init'] == 'fresh':
                credit.unlink(missing_ok=True)
            credit.parent.mkdir(parents=True, exist_ok=True)
        plan = plan_for_mission(item, None, mode='monotone', advice_file=str(tmp / t['advice']['file']),
                                credit_path=str(credit) if credit else None)
        first = plan['first_station']
        run_id = f"run_{t['id']}"
        m = {'memory': plan, 'events': []}
        if first == holder:
            m.update(checkpoint_station=holder, checkpoint=cp(item, item, True))
        else:
            m.update(recovery={'first_station': first, 'first_checkpoint': cp(item, OTHER[item], False,
                                                                                 'local_vlm_disagree_or_wrong_supply')},
                     checkpoint_station=holder, checkpoint=cp(item, item, True))
        final = holder if wrong_station_unsafe is None or t['id'] != wrong_station_unsafe else OTHER[holder]
        d = runs / run_id
        d.mkdir()
        if t['id'] not in no_json:
            (d / 'mission.json').write_text(json.dumps(m))
            if credit is not None:
                orch.advice_audit(d)
                orch.settle_credit(d, str(credit), run_id)
        n_visits = len(ac.visits_from_mission(m))
        rows.append({'trial_id': t['id'], 'run_id': run_id, 'state': 'COMPLETED', 'final': True, 'final_station': final,
                     'observed_action': 'ALLOW_AFTER_SEARCH' if 'recovery' in m else 'ALLOW',
                     'mission_time_s': 60.0 + time_per_visit * (n_visits - 1)})
    return rows


class ProtocolB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mpb.build()

    def test_size_determinism_ids(self):
        p = self.p
        self.assertEqual(p['planned_n'], 48)
        self.assertEqual(json.dumps(mpb.build(), sort_keys=True), json.dumps(p, sort_keys=True))
        self.assertEqual(len({t['id'] for t in p['trials']}), 48)
        self.assertEqual([t['order'] for t in p['trials']], list(range(1, 49)))
        self.assertEqual({s: v['condition'] for s, v in p['sequences'].items()},
                         {'BL1': 'liar', 'BL2': 'liar', 'BL3': 'liar', 'BH1': 'honest'})
        self.assertEqual(rc.load_protocol(str(ROOT / 'experiments/campaign_b_protocol.json'))[0]['id'], 'B001')

    def test_registered_files_equal_the_generator(self):
        self.assertEqual(json.loads((ROOT / 'experiments/campaign_b_protocol.json').read_text()), json.loads(json.dumps(self.p)))
        pilot = mpb.build(**mpb.PILOT)
        self.assertEqual(json.loads((ROOT / 'experiments/campaign_b_pilot_protocol.json').read_text()), json.loads(json.dumps(pilot)))
        for rel, items in self.p['advice_files'].items():
            self.assertEqual(json.loads((ROOT / rel).read_text()), items)

    def test_structure(self):
        by = {}
        for t in self.p['trials']:
            by.setdefault((t['sequence'], t['config']), []).append(t)
        self.assertEqual(len(by), 8)
        for (seq, arm), ts in by.items():
            ks = [t['mission_index'] for t in sorted(ts, key=lambda t: t['order'])]
            self.assertEqual(ks, [1, 2, 3, 4, 5, 6])                      # a ledger is only valid if missions run in order
            self.assertEqual(len({t['advice']['file'] for t in ts}), 1)    # the SAME advice file every mission
            self.assertEqual(len({t['expected'] for t in ts}), 1)          # same requested supply in a sequence
            self.assertEqual(len({t['scene'] for t in ts}), 1)
            for t in ts:
                self.assertEqual(t['advice']['mode'], 'monotone')
                if arm == 'credit':
                    self.assertEqual(t['advice_credit']['init'], 'fresh' if t['mission_index'] == 1 else 'keep')
                    self.assertEqual(t['advice_credit']['file'], f'experiments/results/credit_B/{seq}_credit.json')
                else:
                    self.assertNotIn('advice_credit', t)
        for seq in self.p['sequences']:     # both arms of a (sequence, mission) share the world and the instruction
            for k in range(1, 7):
                a, b = [t for t in self.p['trials'] if t['sequence'] == seq and t['mission_index'] == k]
                self.assertEqual((a['world_spec'], a['instruction']), (b['world_spec'], b['instruction']))
        self.assertEqual(len({json.dumps(t['world_spec'], sort_keys=True) for t in self.p['trials']}), 24)

    def test_advice_is_the_other_station_and_scene_decides_truth(self):
        for seq, s in self.p['sequences'].items():
            items = self.p['advice_files'][s['advice_file']]
            self.assertEqual([(a['source'], a['kind'], a['station']) for a in items], [('peer', 'location', OTHER[s['item']])])
            self.assertEqual(s['scene'], 'nominal' if s['condition'] == 'liar' else 'swapped')
        self.assertEqual({self.p['sequences'][s]['item'] for s in ('BL1', 'BL2', 'BL3')}, {'water', 'medicine'})

    def test_predictions(self):
        for t in self.p['trials']:
            item = t['expected']
            if t['condition'] == 'honest':
                self.assertEqual((t['expected_first_station'], t['expected_wasted_visits'], t['expected_throttled']),
                                 (OTHER[item], 0, 0))
            elif t['config'] == 'nocredit' or t['mission_index'] <= 2:
                self.assertEqual((t['expected_first_station'], t['expected_wasted_visits'], t['expected_throttled']),
                                 (OTHER[item], 1, 0))
            else:
                self.assertEqual((t['expected_first_station'], t['expected_wasted_visits'], t['expected_throttled'], t['expected_action']),
                                 (item, 0, 1, 'ALLOW'))

    def test_pilot_is_separate(self):
        pilot = mpb.build(**mpb.PILOT)
        self.assertEqual((pilot['planned_n'], pilot['m']), (6, 3))
        self.assertNotEqual(pilot['seed'], self.p['seed'])
        self.assertTrue(set(pilot['advice_files']).isdisjoint(self.p['advice_files']))
        self.assertTrue({t['advice_credit']['file'] for t in pilot['trials'] if 'advice_credit' in t}.isdisjoint(
            {t['advice_credit']['file'] for t in self.p['trials'] if 'advice_credit' in t}))


class CreditFlags(unittest.TestCase):
    def test_default_off_and_flags(self):
        self.assertEqual(rc.advice_flags({'mode': 'monotone', 'file': 'x.json'}), ['--advice-mode', 'monotone', '--advice-file', str(ROOT / 'x.json')])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rc, 'ROOT', Path(d)):
            fl = rc.credit_flags({'file': 'led/s_credit.json', 'init': 'keep'}, {'mode': 'monotone', 'file': 'a.json'})
            self.assertEqual(fl, ['--advice-credit', str(Path(d) / 'led/s_credit.json')])
            self.assertTrue((Path(d) / 'led').is_dir())

    def test_fresh_deletes_keep_keeps(self):
        adv = {'mode': 'monotone', 'file': 'a.json'}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rc, 'ROOT', Path(d)):
            f = Path(d) / 'l.json'
            f.write_text('{}')
            rc.credit_flags({'file': 'l.json'}, adv)                 # default init = keep
            self.assertTrue(f.exists())
            rc.credit_flags({'file': 'l.json', 'init': 'keep'}, adv)
            self.assertTrue(f.exists())
            rc.credit_flags({'file': 'l.json', 'init': 'fresh'}, adv)
            self.assertFalse(f.exists())
            rc.credit_flags({'file': 'l.json', 'init': 'fresh'}, adv)    # nothing to delete: no error

    def test_bad_specs(self):
        for spec, adv in [({}, {'mode': 'monotone', 'file': 'a'}), ({'file': 'l', 'init': 'x'}, {'mode': 'monotone', 'file': 'a'}),
                          ({'file': 'l', 'extra': 1}, {'mode': 'monotone', 'file': 'a'}), ({'file': 'l'}, None),
                          ({'file': 'l'}, {'mode': 'naive', 'file': 'a'}), ({'file': 'l'}, {'mode': 'monotone'}),
                          ({'file': 'l'}, {'mode': 'off', 'from_instruction': True})]:
            with self.subTest(spec=spec, adv=adv), self.assertRaises(SystemExit):
                rc.credit_flags(spec, adv)

    def test_instruction_channel_is_allowed(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rc, 'ROOT', Path(d)):
            self.assertEqual(rc.credit_flags({'file': 'l'}, {'mode': 'monotone', 'from_instruction': True})[0], '--advice-credit')

    def test_main_passes_the_flag_only_for_credit_trials(self):
        src = (ROOT / 'scripts/run_campaign.py').read_text()
        self.assertIn("credit_flags(trial['advice_credit'], adv)", src)
        self.assertIn("if trial.get('advice_credit'):", src)


class AnalysisB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def world(self, name, **kw):
        tmp = self.tmp / name
        tmp.mkdir()
        proto = mpb.build(advice_dir=str(tmp / 'adv'), credit_dir='credit')
        for rel, items in proto['advice_files'].items():
            Path(rel).parent.mkdir(parents=True, exist_ok=True)
            Path(rel).write_text(json.dumps(items))
        for t in proto['trials']:                                    # advice files are absolute here
            t['advice']['file'] = str(Path(t['advice']['file']).relative_to(tmp)) if str(t['advice']['file']).startswith(str(tmp)) else t['advice']['file']
        return tmp, proto, simulate(proto, tmp, **kw)

    def run_analysis(self, tmp, proto, rows):
        return ba.analyse(proto, rows, tmp / 'runs', tmp)

    def test_full_campaign_as_registered(self):
        tmp, proto, rows = self.world('ok')
        s = self.run_analysis(tmp, proto, rows)
        self.assertEqual(s['n_runs'], 48)
        self.assertTrue(s['B1_liar']['supported'], s['B1_liar'])
        for seq, v in s['B1_liar']['sequences'].items():
            self.assertEqual((v['wasted_nocredit'], v['wasted_credit']), (6, 2))
            self.assertTrue(v['within_prop3_bound'])
        self.assertEqual(s['per_sequence']['BL1']['credit']['throttled'], [0, 0, 1, 1, 1, 1])
        self.assertEqual(s['per_sequence']['BL1']['credit']['wasted_per_mission'], [1, 1, 0, 0, 0, 0])
        self.assertTrue(s['B2_honest']['supported'], s['B2_honest'])
        self.assertEqual(s['per_sequence']['BH1']['credit']['throttled'], [0] * 6)
        b3 = s['B3_audits']
        self.assertTrue(b3['supported'], b3)
        self.assertEqual((b3['runs_audited'], b3['unsafe_deliveries'], b3['audit_failures']), (48, [], []))
        self.assertTrue(all(v['ok'] and v['checked'] for v in b3['ledger_replay'].values()))
        self.assertEqual(s['B3_audits']['ledger_replay']['BL1']['offline_credit']['file']['loc'], 0.0)
        self.assertEqual(s['B3_audits']['ledger_replay']['BH1']['offline_credit']['file']['loc'], ac.C_LOC)
        b4 = s['B4_time_descriptive']       # a wasted visit costs 40 s in the stand-in: W = 40, 4 missions saved
        self.assertEqual((b4['W_s'], b4['predicted_saving_per_sequence_s'], b4['median_saving_s']), (40.0, 160.0, 160.0))
        self.assertTrue(s['headline_supported'])

    def test_b5_interlock_permits(self):
        tmp, proto, rows = self.world('b5')
        self.assertIn('--delivery-interlock', proto['common_stack_args'])
        for r in rows:                     # what the orchestrator records: one permit per delivered run
            r['interlock_audit'] = {'permits': 1 if r.get('observed_action', '').startswith('ALLOW') else 0}
        s = self.run_analysis(tmp, proto, rows)
        self.assertTrue(s['B5_interlock']['supported'], s['B5_interlock'])
        rows[0]['interlock_audit'] = {'permits': 0}          # a delivery without a permit
        s = self.run_analysis(tmp, proto, rows)
        self.assertFalse(s['B5_interlock']['supported'])
        self.assertIn(proto['trials'][0]['id'] if rows[0].get('trial_id') is None else rows[0]['trial_id'], s['B5_interlock']['violations'])

    def test_main_writes_summary_and_pilot_check(self):
        tmp, proto, rows = self.world('main')
        pp, lp = tmp / 'p.json', tmp / 'l.jsonl'
        pp.write_text(json.dumps(proto))
        lp.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        out = tmp / 'b_summary.json'
        self.assertEqual(ba.main(['--protocol', str(pp), '--ledger', str(lp), '--runs-dir', str(tmp / 'runs'), '--root', str(tmp),
                                  '--out', str(out)]), 0)
        self.assertTrue(json.loads(out.read_text())['headline_supported'])
        self.assertEqual(ba.main(['--pilot', '--protocol', str(pp), '--ledger', str(lp), '--runs-dir', str(tmp / 'runs'),
                                  '--root', str(tmp)]), 0)

    def test_pilot_protocol(self):
        tmp = self.tmp / 'pilot'
        tmp.mkdir()
        proto = mpb.build(**dict(mpb.PILOT, advice_dir=str(tmp / 'adv'), credit_dir='credit'))
        for rel, items in proto['advice_files'].items():
            Path(rel).parent.mkdir(parents=True, exist_ok=True)
            Path(rel).write_text(json.dumps(items))
        rows = simulate(proto, tmp)
        res = ba.pilot_check(proto, rows, tmp / 'runs', tmp)
        self.assertTrue(res['ok'], res)
        res = ba.pilot_check(proto, rows[:-1], tmp / 'runs', tmp)         # a missing run
        self.assertFalse(res['ok'])

    def test_credit_not_applied_breaks_b1(self):
        tmp, proto, rows = self.world('nocredit', ignore_credit=True)
        s = self.run_analysis(tmp, proto, rows)
        self.assertFalse(s['B1_liar']['supported'])
        self.assertEqual({v['wasted_credit'] for v in s['B1_liar']['sequences'].values()}, {6})
        self.assertFalse(s['B1_liar']['bound_held'])
        self.assertFalse(s['B3_audits']['supported'])          # credit arm without credit audit / ledger

    def test_tampered_ledger_fails_b3(self):
        tmp, proto, rows = self.world('tamper')
        f = tmp / 'credit/BL2_credit.json'
        led = json.loads(f.read_text())
        led['history'][1]['charges'][0]['charge'] = 0.0
        f.write_text(json.dumps(led))
        s = self.run_analysis(tmp, proto, rows)
        self.assertEqual(s['B3_audits']['ledger_replay_failures'], ['BL2'])
        self.assertFalse(s['B3_audits']['supported'])
        self.assertTrue(s['B1_liar']['supported'])              # the behaviour is unaffected; only the bookkeeping failed

    def test_missing_ledger_file_and_missing_runs_are_graceful(self):
        tmp, proto, rows = self.world('missing', drop=('B001', 'B002', 'B010'))
        (tmp / 'credit/BL1_credit.json').unlink(missing_ok=True)
        s = self.run_analysis(tmp, proto, rows)
        self.assertEqual(len(s['missing_runs']), 3)
        self.assertTrue(set(s['sequences_dropped']) >= {x['sequence'] for x in proto['trials'] if x['id'] in ('B001', 'B002', 'B010')})
        self.assertIsInstance(s['B1_liar']['supported'], bool)
        self.assertEqual(ba.analyse(proto, [], tmp / 'runs', tmp)['B1_liar']['supported'], False)     # no runs at all
        self.assertFalse(ba.analyse(proto, [], tmp / 'runs', tmp)['headline_supported'])

    def test_run_without_mission_json_is_reported(self):
        tmp, proto, rows = self.world('nojson', no_json=('B005',))
        s = self.run_analysis(tmp, proto, rows)
        self.assertEqual(s['B3_audits']['runs_without_mission_json'], ['B005'])
        self.assertFalse(s['B3_audits']['supported'])

    def test_unsafe_delivery_is_counted(self):
        tmp, proto, rows = self.world('unsafe', wrong_station_unsafe='B003')
        s = self.run_analysis(tmp, proto, rows)
        self.assertEqual(s['B3_audits']['unsafe_deliveries'], ['B003'])
        self.assertFalse(s['B3_audits']['supported'])

    def test_failed_run_drops_its_sequence(self):
        tmp, proto, rows = self.world('failed')
        rows = [dict(r, observed_action='FAILED') if r['trial_id'] == 'B004' else r for r in rows]
        s = self.run_analysis(tmp, proto, rows)
        seq = next(t['sequence'] for t in proto['trials'] if t['id'] == 'B004')
        self.assertIn(seq, s['sequences_dropped'])
        self.assertEqual(s['B1_liar']['n_complete'] + s['B2_honest']['n_complete'], 3)
        self.assertEqual(s['B1_liar']['supported'], s['B1_liar']['n_complete'] >= 2)

    def test_retried_attempt_rows_are_ignored(self):
        tmp, proto, rows = self.world('retry')
        stale = dict(rows[0], observed_action='FAILED', final=False)
        s = self.run_analysis(tmp, proto, [stale] + rows)
        self.assertTrue(s['B1_liar']['supported'])


if __name__ == '__main__':
    unittest.main()


class RunScript(unittest.TestCase):
    def test_b_run_gate_and_syntax(self):
        import subprocess
        sh = ROOT / 'scripts/b_run.sh'
        self.assertEqual(subprocess.run(['bash', '-n', str(sh)]).returncode, 0)
        src = sh.read_text()
        for needle in ('B_DONE', 'B_ABORT', 'git ls-files --error-unmatch', 'git diff --quiet HEAD', "Status: REGISTERED",
                       'campaign_b_pilot_protocol.json', 'b_analysis.py --pilot', 'scripts/run_campaign.py --protocol'):
            self.assertIn(needle, src)
        self.assertLess(src.index('B_REGISTERED'), src.index('b_analysis.py --pilot'))     # the gate comes before the pilot
        self.assertLess(src.index('b_analysis.py --pilot'), src.index('--ledger "$RES/campaign_B_ledger.jsonl"'))
        self.assertNotIn('--advice-credit', src)         # the flags come from the protocol trials, not from the script

    def test_prereg_has_a_status_and_the_predictions(self):
        txt = (ROOT / 'experiments/PREREGISTRATION_B.md').read_text()
        self.assertTrue(txt.startswith('# Pre-registration'))
        self.assertRegex(txt, r'\nStatus: (DRAFT|REGISTERED)\n')
        for needle in ('B1', 'B2', 'B3', 'B4', 'exactly 6', 'exactly 2', 'Default-off elsewhere', 'What failure would mean'):
            self.assertIn(needle, txt)
