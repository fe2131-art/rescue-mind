import unittest
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from scripts.submission_preflight import inspect_submission
from rescuemind.experiment_stats import validate_unique

ROOT=Path(__file__).resolve().parents[1]

class TestArtifactQuality(unittest.TestCase):
    def test_sdf_valid_xml_components(self):
        root=ET.parse(ROOT/'worlds/rescuemind_test_arena.sdf').getroot()
        self.assertEqual(root.tag,'sdf')
        models={m.attrib['name'] for m in root.findall('.//world/model')}
        self.assertTrue({'rescue_diffbot','aid_station_water','aid_station_medicine','shelter_B'}<=models)
        self.assertEqual(len(root.findall('.//model[@name="rescue_diffbot"]//sensor')),2)
        self.assertEqual(len(root.findall('.//model[@name="rescue_diffbot"]//joint')),2)
        # DiffDrive + OdometryPublisher (simulator ground truth for independent audits, v3.3)
        plugins=[p.get('name') for p in root.findall('.//model[@name="rescue_diffbot"]//plugin')]
        self.assertEqual(sorted(plugins),['gz::sim::systems::DiffDrive','gz::sim::systems::OdometryPublisher'])
    def test_submissions_do_not_accept_old_preview(self):
        with tempfile.TemporaryDirectory() as td:
            r=inspect_submission(str(Path(td)/'missing.pdf'),str(ROOT/'outputs/grid_prototype_preview.mp4'),
                'https://github.com/team/project','https://youtu.be/abc123','name')
            self.assertFalse(r['automatable_pass'])
            self.assertFalse(r['submission_ready'])
    def test_distinct_frames_required_even_if_same_pair(self):
        rows=[{'id':'a','image_sha256':{'supply':'a'*64,'corridor':'b'*64}},
              {'id':'b','image_sha256':{'supply':'a'*64,'corridor':'b'*64}}]
        with self.assertRaisesRegex(ValueError,'Duplicate supply'):
            validate_unique(rows)

if __name__=='__main__':unittest.main()
