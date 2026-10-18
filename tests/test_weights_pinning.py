"""Trust base: the server reports the Hugging Face snapshot it loaded; the client refuses any other pinned revision."""
import unittest

from rescuemind.local_vision import local_decision, PINNED_REVISIONS, LocalInferenceError, weights_verified

MODEL = 'Qwen/Qwen3.5-9B'      # the v3.6 model


def call(rev=None):
    c = {'backend': 'local_transformers', 'real_inference': True, 'model': MODEL, 'image_sha256': 'a',
         'result': {'supply': 'water', 'scene': 'clear'}, 'scores': {'hazard_prob': 0.0, 'supply_probs': {'water': 0.9}}}
    if rev is not None:
        c['weights_revision'] = rev
    return c


class Pinning(unittest.TestCase):
    def test_pinned_revision_passes(self):
        r = PINNED_REVISIONS[MODEL]
        self.assertTrue(local_decision('water', call(r), call(r))['allow'])
        self.assertTrue(weights_verified(call(r)))

    def test_other_revision_is_refused(self):
        with self.assertRaises(LocalInferenceError):
            local_decision('water', call('0' * 40), call(PINNED_REVISIONS[MODEL]))

    def test_missing_revision_is_unverified_not_refused(self):
        self.assertIsNone(weights_verified(call()))
        self.assertTrue(local_decision('water', call(), call())['allow'])

    def test_server_reads_the_snapshot_commit(self):
        import importlib.util, os
        from pathlib import Path
        spec = importlib.util.spec_from_file_location('srv', Path(__file__).resolve().parents[1] / 'scripts/local_vlm_server.py')
        try:
            srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv)
        except Exception as e:          # the server needs torch etc. only at model load; skip if the import itself fails
            self.skipTest(f'server import: {e}')
        rev = srv.weights_revision(MODEL)
        if rev is None:
            self.skipTest('model not in this cache')
        self.assertEqual(rev, PINNED_REVISIONS[MODEL])


if __name__ == '__main__':
    unittest.main()
