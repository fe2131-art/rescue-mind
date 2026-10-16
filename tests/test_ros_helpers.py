import unittest
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class TestROSHelpers(unittest.TestCase):
    def test_world_parser(self):
        gz=load('spawn_box',ROOT/'ros/spawn_box.py')
        self.assertEqual(gz.available_worlds('/world/empty/create\n/world/sandbox/create\n/world/empty/control'),['empty','sandbox'])

    def test_valid_sdf(self):
        import tempfile
        import xml.etree.ElementTree as ET
        gz=load('spawn_box',ROOT/'ros/spawn_box.py')
        with tempfile.TemporaryDirectory() as td:
            filename=gz.write_obstacle(Path(td)/'box.sdf',1.0,2.0)
            tree=ET.parse(filename)
            self.assertEqual(tree.getroot().tag,'sdf')
            self.assertEqual(tree.find('.//static').text,'true')

    def test_dry_run_poses(self):
        mod=load('nav2_mission',ROOT/'ros/nav2_mission.py')
        data,intent,steps=mod.mission('避難所Aへ医薬品を配送してください','tfidf',str(ROOT/'configs/poses.example.json'))
        self.assertEqual(intent.item,'medicine')
        self.assertEqual(steps[0][1],'medicine')
        self.assertEqual(steps[1][1],'A')

if __name__=='__main__':
    unittest.main()
