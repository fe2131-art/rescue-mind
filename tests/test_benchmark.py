import unittest
from itertools import product
from rescuemind.benchmark_vision import aggregate, validate_record
from rescuemind.safety import decide


def jev(s='water', scene='clear', present=.98, conf=.93, hazard=.01):
    return {'real_model':True,'model':'jev-1.14.0','supply':s,'scene':scene,
            'supply_confidence':conf,'supply_present_probability':present,'hazard_probability':hazard}

def qwen(s='water',scene='clear'):
    return {'real_model':True,'model':'qwen3.8-omni-flash','supply':s,'scene':scene}

class TestBenchmark(unittest.TestCase):
    def test_fault_injection_enumeration(self):
        count=0; allows=0
        for js,qs,jscene,qscene,present,confidence,hazard in product(
            ('water','medicine','other'),('water','medicine','other'),
            ('clear','hazard','unknown'),('clear','hazard','unknown'),
            (.3,.95),(.4,.93),(.01,.9)):
            count+=1
            d=decide('water',jev(js,jscene,present,confidence,hazard),qwen(qs,qscene))
            expected=(js=='water' and qs=='water' and jscene=='clear' and qscene=='clear'
                      and present>=.8 and confidence>=.65 and hazard<=.2)
            self.assertEqual(d.allow,expected, msg=f'{js} {qs} {jscene} {qscene} {present} {confidence} {hazard}')
            allows+=int(d.allow)
        self.assertEqual(count,648)
        self.assertEqual(allows,1)

    def test_benchmark_three_modes(self):
        row={'id':'real-test','provenance':'live_api_capture','expected':'water',
             'truth':{'supply':'water','scene':'clear'},
             'supply':{'jev':jev(),'qwen':qwen()},'corridor':{'jev':jev(),'qwen':qwen()}}
        result=aggregate([row])
        self.assertEqual(result['results']['fusion']['coverage'],1)
        row2={**row,'id':'unsafe','truth':{'supply':'medicine','scene':'hazard'}}
        result=aggregate([row2])
        self.assertEqual(result['results']['fusion']['unsafe_approved'],1)

    def test_fake_record_rejected(self):
        with self.assertRaises(ValueError):
            validate_record({'id':'fake','truth':{'supply':'water','scene':'clear'},'expected':'water','supply':{'jev':jev(),'qwen':qwen()}, 'corridor':{'jev':jev(),'qwen':qwen()},'provenance':'synthetic'})

    def test_fusion_disagreement(self):
        self.assertEqual(decide('water',jev(),qwen('medicine')).reason,'supply_mismatch_or_disagreement')

if __name__=='__main__':unittest.main()
