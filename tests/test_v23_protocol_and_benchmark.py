import copy,hashlib,json,unittest,tempfile
from pathlib import Path
from rescuemind.v23_protocol import make_protocol,validate_protocol,dump_protocol
from rescuemind.v23_strict_benchmark import validate_cases,evaluate,ProtocolEvidenceError


def record(t,n,jev_supply=None,qwen_supply=None):
    truth=t['truth_supply'];label=jev_supply or truth;qlabel=qwen_supply or truth
    supply_j={'real_model':True,'model':'jev-1.14.0','supply':label,'supply_confidence':.92,'supply_present_probability':.91 if label!='other' else .04,'scene':'unknown','hazard_probability':.0}
    supply_q={'real_model':True,'model':'qwen3.8-omni-flash','supply':qlabel,'scene':'unknown'}
    corridor_j={'real_model':True,'model':'jev-1.14.0','supply':'other','scene':'clear','hazard_probability':.02}
    corridor_q={'real_model':True,'model':'qwen3.8-omni-flash','supply':'other','scene':'clear'}
    return {'id':t['id'],'expected':t['expected'],'truth':{'supply':truth,'scene':'clear'},
            'provenance':'live_api_capture','wall_sec':2.5,
            'image_sha256':{'supply':hashlib.sha256(('s'+str(n)).encode()).hexdigest(),
                            'corridor':hashlib.sha256(('c'+str(n)).encode()).hexdigest()},
            'supply':{'jev':supply_j,'qwen':supply_q},'corridor':{'jev':corridor_j,'qwen':corridor_q}}

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.p=make_protocol(2,20261016)
        self.r=[record(t,i) for i,t in enumerate(self.p['trials'])]
    def test_preregistration_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'protocol.json'
            dump_protocol(path,2,11)
            self.assertEqual(dump_protocol(path,2,11)['seed'],11)
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                dump_protocol(path,2,12)
            self.assertEqual(json.loads(path.read_text())['seed'],11)
    def test_balance(self):
        self.assertEqual(len(self.p['trials']),12)
        self.assertEqual(len({(x['scene'],x['expected'],x['repeat']) for x in self.p['trials']}),12)
        self.assertEqual(make_protocol(2,20261016),self.p)
    def test_locked_tamper(self):
        p=copy.deepcopy(self.p);p['trials'][0]['truth_supply']='medicine' if p['trials'][0]['truth_supply']!='medicine' else 'water'
        with self.assertRaises(ValueError):validate_protocol(p)
    def test_full_metrics(self):
        out=evaluate(self.p,self.r)
        self.assertTrue(out['complete']);self.assertEqual(out['coverage']['captured_n'],12)
        self.assertEqual(set(out['by_scene']),{'nominal','swapped','empty'})
        self.assertIn('false_denial',out['metrics']['results']['fusion'])
    def test_missing_fails_by_default(self):
        with self.assertRaisesRegex(ProtocolEvidenceError,'incomplete study'):evaluate(self.p,self.r[:-1])
        out=evaluate(self.p,self.r[:-1],allow_partial=True)
        self.assertEqual(out['report_status'],'PRELIMINARY_INCOMPLETE')
    def test_duplicate_case_fails(self):
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,self.r+[self.r[0]])
    def test_duplicate_image_fails(self):
        r=copy.deepcopy(self.r);r[1]['image_sha256']=r[0]['image_sha256']
        with self.assertRaises(ValueError):validate_cases(self.p,r)
    def test_wrong_scene_truth_fails(self):
        r=copy.deepcopy(self.r);r[0]['truth']['supply']='water' if r[0]['truth']['supply']!='water' else 'medicine'
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_mock_fails(self):
        r=copy.deepcopy(self.r);r[0]['provenance']='synthetic_mock'
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_wrong_model_fails(self):
        r=copy.deepcopy(self.r);r[0]['supply']['jev']['model']='jev-latest'
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
        r=copy.deepcopy(self.r);r[0]['corridor']['qwen']['model']='qwen3-vl'
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_image_integrity(self):
        r=copy.deepcopy(self.r);r[0]['image_sha256']['supply']='a'*64;r[0]['image_sha256']['corridor']='a'*64
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_bool_latency_rejected(self):
        r=copy.deepcopy(self.r);r[0]['wall_sec']=True
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_no_records_fails(self):
        with self.assertRaises(ProtocolEvidenceError):evaluate(self.p,[])
    def test_unknown_id_fails(self):
        r=copy.deepcopy(self.r);r[0]['id']='R999'
        with self.assertRaises(ProtocolEvidenceError):validate_cases(self.p,r)
    def test_no_false_safety_claim(self):
        out=evaluate(self.p,self.r)
        self.assertIn('SELF_ASSERTED',out['scope'])
        self.assertIn('correlated',' '.join(out['limitations']))

if __name__=='__main__':unittest.main()
