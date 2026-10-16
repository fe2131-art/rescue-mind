import unittest
import json
from math import nan
from rescuemind.watchdog import Watchdog
from rescuemind.streaming import accumulate_chat_chunks, StreamError
from rescuemind.experiment_stats import wilson_interval, validate_unique
from rescuemind.safety import decide
from rescuemind.benchmark_vision import aggregate

class TestStreaming(unittest.TestCase):
    def test_aggregate_sse_model_and_usage(self):
        lines = [
            'data: '+json.dumps({'model':'qwen3.8-omni-flash','choices':[{'index':0,'delta':{'content':'{"supply":"water",'}}]})+'\n',
            'data: '+json.dumps({'model':'qwen3.8-omni-flash','choices':[{'index':0,'delta':{'content':'"scene":"clear"}'},'finish_reason':'stop'}]})+'\n',
            'data: '+json.dumps({'model':'qwen3.8-omni-flash','choices':[],'usage':{'total_tokens':150}})+'\n',
            'data: [DONE]\n']
        got=accumulate_chat_chunks([x.encode() for x in lines])
        self.assertEqual(json.loads(got['choices'][0]['message']['content']), {'supply':'water','scene':'clear'})
        self.assertEqual(got['usage']['total_tokens'], 150)
    def test_missing_done_fails(self):
        with self.assertRaises(StreamError):
            accumulate_chat_chunks(['data: {"model":"qwen3.8-omni-flash","choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}'])
    def test_malformed_stream_fails(self):
        with self.assertRaises(StreamError):
            accumulate_chat_chunks(['data: [THIS IS NOT JSON]','data: [DONE]'])
    def test_model_switch_fails(self):
        with self.assertRaisesRegex(StreamError,'Changed model'):
            accumulate_chat_chunks(['data: {"model":"A","choices":[]}', 'data: {"model":"B","choices":[]}', 'data: [DONE]'])
    def test_stream_capacity(self):
        with self.assertRaisesRegex(StreamError,'cap'):
            accumulate_chat_chunks(['data: '+'x'*500], max_bytes=10)

class TestWatchdog(unittest.TestCase):
    def make(self):return Watchdog(min_front_m=.35,started_at=0,startup_grace_s=3,max_scan_age_s=2)
    def test_scan_clear(self):
        w=self.make();w.update_scan([1.0]*31,-.3,.02,.10,6,1.0)
        self.assertIsNone(w.check(1.2))
    def test_obstacle_latches(self):
        w=self.make();w.update_scan([1.]*15+[.2]+[1.]*15,-.3,.02,.1,6,1)
        self.assertEqual(w.check(1.1),'front_obstacle_too_close')
        w.update_scan([5.]*31,-.3,.02,.1,6,2)
        self.assertEqual(w.check(2),'front_obstacle_too_close')
    def test_no_scan_fails(self):
        self.assertEqual(self.make().check(3.1),'no_lidar_scan')
    def test_stale_scan_fails(self):
        w=self.make();w.update_scan([1.]*31,-.3,.02,.1,6,1)
        self.assertEqual(w.check(3.1),'stale_lidar_scan')
    def test_estop(self):
        w=self.make();w.emergency_stop(True)
        self.assertEqual(w.check(.1),'operator_emergency_stop')
    def test_no_return_is_clear_but_nan_is_unobservable(self):
        w=self.make();w.update_scan([float('inf')]*31,-.3,.02,.1,6,1)
        self.assertIsNone(w.check(1))  # ROS +inf: no return up to range_max
        self.assertEqual(w.last_front_m,6)
        v=self.make();v.update_scan([float('nan')]*31,-.3,.02,.1,6,1)
        self.assertEqual(v.check(1),'front_scan_unobservable')
    def test_sensor_close_fails(self):
        w=self.make();w.update_scan([.05]*31,-.3,.02,.1,6,1)
        self.assertEqual(w.check(1),'front_range_below_sensor_min')
    def test_rear_obstacle_not_in_front(self):
        w=self.make();w.update_scan([0.2]+[1.]*360,-3.141592653589793,3.141592653589793/180,.1,6,1)
        self.assertIsNone(w.check(1))

class TestAnalysis(unittest.TestCase):
    def test_wilson_edges(self):
        self.assertIsNone(wilson_interval(0,0))
        self.assertEqual(wilson_interval(0,10)[0],0)
        self.assertEqual(wilson_interval(10,10)[1],1)
        with self.assertRaises(ValueError):wilson_interval(2,1)
    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            validate_unique([{'id':'a'},{'id':'a'}])
    def test_duplicate_images_rejected(self):
        r=lambda i:{'id':i,'image_sha256':{'supply':'a'*64,'corridor':'b'*64}}
        with self.assertRaisesRegex(ValueError,'Duplicate supply'):
            validate_unique([r('a'),r('b')])
    def test_nan_fails_closed(self):
        j={'real_model':True,'supply':'water','scene':'clear','supply_confidence':nan,
           'hazard_probability':.0,'supply_present_probability':.9}
        q={'real_model':True,'supply':'water','scene':'clear'}
        self.assertFalse(decide('water',j,q).allow)

if __name__ == '__main__': unittest.main()
