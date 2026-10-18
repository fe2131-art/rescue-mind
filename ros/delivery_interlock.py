"""I-22 delivery interlock node (default off; started by the orchestrator with --delivery-interlock).

Independent of the mission node: subscribes /rescuemind/approval_record, recomputes the decision from the saved model
outputs (rescuemind.delivery_interlock), and publishes a time-limited permit on /rescuemind/delivery_permit at 2 Hz while
the latest record is approved.  The velocity guard (guarded_cmd_relay.py --delivery-interlock) forwards motion during the
'deliver' phase only with a valid permit.  Must not import the mission node.

WARNING: simulation only, not safety-certified.  Same-host assumption: the saved images and model outputs are trusted as
written; the key file (mode 0600) is what separates the permit from a mission node that can only write topics.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import delivery_permit as dp
from rescuemind.delivery_interlock import Interlock, Policy


def run(args):
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from rescuemind.ros_qos import control_qos
    key = dp.load_key(args.key_file) if args.key_file else None
    core = Interlock(Policy(require_look_around=args.require_look_around, require_adaptive=args.require_adaptive,
                            image_root=args.image_root, hazard_threshold=args.hazard_threshold), key=key, ttl_s=args.ttl, max_life_s=args.max_life)
    log = Path(args.log) if args.log else None

    def write(row):
        if log is not None:
            with log.open('a', encoding='utf8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

    class Node_(Node):
        def __init__(self):
            super().__init__('rescuemind_delivery_interlock')
            q = control_qos('reliable')
            self.permit_pub = self.create_publisher(String, dp.TOPIC_PERMIT, q)
            self.decision_pub = self.create_publisher(String, dp.TOPIC_DECISION, q)
            self.create_subscription(String, dp.TOPIC_RECORD, self.on_record, q)
            self.create_timer(args.period, self.on_tick)
            self.issued = set()
            write({'event': 'start', 't_unix': time.time(), 'hmac': key is not None, 'ttl_s': args.ttl,
                   'policy': vars(args)})

        def on_record(self, msg):
            d = core.on_record(msg.data, time.time())
            if d is not None:
                row = dict(d.as_dict(), event='decision', t_unix=time.time())
                write(row)
                self.decision_pub.publish(String(data=json.dumps(row)))
                self.get_logger().info(f'record {d.record_hash[:12]}: ' + ('PERMIT' if d.permit else 'DENY ' + d.reason))

        def on_tick(self):
            raw = core.tick(time.time())
            if raw is not None:
                self.permit_pub.publish(String(data=raw))

    rclpy.init()
    node = Node_()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file', default=None, help='HMAC key (hex), generated at stack start; shared with the guard only')
    p.add_argument('--ttl', type=float, default=4.0, help='permit lifetime (s); re-issued every --period while approved')
    p.add_argument('--period', type=float, default=0.5)
    p.add_argument('--max-life', type=float, default=240.0, help='longest time one record keeps being permitted (s)')
    p.add_argument('--log', default=None, help='JSONL of decisions (audited by the orchestrator)')
    p.add_argument('--image-root', default=None, help='the record images must lie under this directory')
    p.add_argument('--hazard-threshold', type=float, default=None,
                   help='the server tau_h every model call must record (default 0.05 = v3.6); a record under another value is denied; '
                        'with --site-config the site value (a conflicting flag is an error)')
    p.add_argument('--site-config', default=None, help='I-26: site.json with the site tau_h (the same file as the server and the mission)')
    p.add_argument('--require-look-around', action='store_true', help='refuse unless side views L and R were taken')
    p.add_argument('--require-adaptive', action='store_true', help='refuse unless the adaptive-view block exists')
    ns = p.parse_args()
    try:
        from rescuemind import real_profile as rp
        site = rp.load_site_config(ns.site_config) if ns.site_config else None
        ns.hazard_threshold = rp.resolve('hazard-threshold', ns.hazard_threshold, site.hazard_threshold if site else None, 0.05)
    except ValueError as e:        # SiteConfigError
        p.error(str(e))
    run(ns)
