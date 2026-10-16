"""Pure fail-closed ROS publisher-topology monitor policy (no ROS import).

An endpoint graph is not a security identity / authentication mechanism. It
rejects common configuration mistakes and newly introduced velocity publishers
*after* the preflight check; it is not a certified physical emergency stop.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

GUARD_NAME = 'rescuemind_velocity_guard'
EXPECTED_TYPE = {'/cmd_vel': 'geometry_msgs/msg/Twist',
                 '/rescuemind/guard_ready': 'std_msgs/msg/Bool'}

# rmw reports this placeholder while a participant's node metadata is still in
# flight (observed live on Jazzy/Fast DDS for ~0.1-1 s after the guard starts).
# It is tolerated ONLY before arming and only for a single correctly typed endpoint.
PENDING_IDENTITY = {'node_name': '_NODE_NAME_UNKNOWN_', 'node_namespace': '_NODE_NAMESPACE_UNKNOWN_'}

class GraphMonitorFault(RuntimeError):
    pass


def endpoints(topic, objects):
    """Convert TopicEndpointInfo or dict objects into normalized structured rows."""
    if topic not in EXPECTED_TYPE:
        raise GraphMonitorFault('unexpected monitored topic')
    rows=[]
    for obj in objects:
        try:
            name=obj['node_name'] if isinstance(obj,dict) else obj.node_name
            namespace=obj['node_namespace'] if isinstance(obj,dict) else obj.node_namespace
            kind=obj['topic_type'] if isinstance(obj,dict) else obj.topic_type
        except (KeyError,AttributeError,TypeError) as e:
            raise GraphMonitorFault('invalid endpoint information') from e
        if not all(isinstance(v,str) and v for v in (name,namespace,kind)):
            raise GraphMonitorFault('invalid endpoint field')
        rows.append({'node_name':name,'node_namespace':namespace,'topic_type':kind})
    return rows


def check_graph(cmd, ready):
    """Allow only one guard publisher for BOTH topics, with exact ROS types."""
    for topic, info in (('/cmd_vel',cmd),('/rescuemind/guard_ready',ready)):
        rows=endpoints(topic,info)
        if len(rows)!=1:
            raise GraphMonitorFault(f'{topic}: expected one guard publisher, found {len(rows)}')
        row=rows[0]
        if row != {'node_name':GUARD_NAME,'node_namespace':'/','topic_type':EXPECTED_TYPE[topic]}:
            raise GraphMonitorFault(f'{topic}: unauthorized/incorrect guard publisher: {row}')
    return True

@dataclass
class RuntimeGuardGraph:
    started_at: float
    startup_grace_s: float = 8.
    last_at: float | None = None
    armed: bool = False
    latched: str | None = None

    def __post_init__(self):
        if not math.isfinite(self.started_at) or not (math.isfinite(self.startup_grace_s) and 0 < self.startup_grace_s <= 60):
            raise ValueError('invalid graph monitor startup settings')

    def observe(self, now: float, cmd, ready) -> str:
        if self.latched:
            raise GraphMonitorFault(self.latched)
        if (not isinstance(now,(int,float)) or not math.isfinite(now) or
            now < self.started_at or (self.last_at is not None and now < self.last_at)):
            self.latched='invalid_graph_monotonic_time'
            raise GraphMonitorFault(self.latched)
        self.last_at=now
        try:
            check_graph(cmd,ready)
        except GraphMonitorFault as exc:
            # During initial DDS discovery, allow a *partial* graph only
            # if every already discovered endpoint is exactly the guard.
            # Duplicates and foreign identities are never given grace; an
            # identity that is still pending when grace expires latches.
            if not self.armed and now-self.started_at <= self.startup_grace_s:
                expected={'node_name':GUARD_NAME,'node_namespace':'/'}
                partial=True
                for topic,group in (('/cmd_vel',cmd),('/rescuemind/guard_ready',ready)):
                    try:
                        rows=endpoints(topic,group)
                    except GraphMonitorFault:
                        partial=False;break
                    if len(rows)>1 or any(row!={**expected,'topic_type':EXPECTED_TYPE[topic]}
                                          and row!={**PENDING_IDENTITY,'topic_type':EXPECTED_TYPE[topic]}
                                          for row in rows):
                        partial=False;break
                if partial:
                    return 'waiting_for_guard_graph'
            self.latched=str(exc)
            raise
        self.armed=True
        return 'sole_guard_confirmed'


def audit_watch_jsonl(path):
    """Validate independent on-disk graph logs; this is NOT authentication."""
    import json
    from pathlib import Path
    file=Path(path)
    if not file.is_file():
        raise GraphMonitorFault('missing runtime guard graph watch log')
    armed=[];prev=-1.
    for line in file.read_text(encoding='utf8').splitlines():
        try:
            row=json.loads(line)
            elapsed=row['elapsed_s'];state=row['state']
            cmd=row['cmd_publishers'];ready=row['guard_ready_publishers']
        except (ValueError,KeyError,TypeError) as exc:
            raise GraphMonitorFault('invalid runtime graph watch evidence') from exc
        if (type(elapsed) not in (float,int) or not math.isfinite(elapsed) or elapsed < 0 or elapsed <= prev
                or type(cmd) is not int or type(ready) is not int):
            raise GraphMonitorFault('runtime graph log timestamps/counts invalid')
        prev=elapsed
        if state=='sole_guard_confirmed':
            if cmd!=1 or ready!=1:
                raise GraphMonitorFault('graph log inconsistent publisher counts')
            armed.append(elapsed)
        elif state!='waiting_for_guard_graph':
            raise GraphMonitorFault('runtime graph watch failed or invalid state')
        elif armed:
            raise GraphMonitorFault('runtime guard graph lost after arming')
    if len(armed)<2 or armed[-1]-armed[0]<.25:
        raise GraphMonitorFault('insufficient runtime publisher watch evidence')
    return {'pass':True,'scope':'ROS_GRAPH_PUBLISHER_COUNTS_ONLY_NOT_AUTHENTICATION',
            'guard_confirmed_samples':len(armed),
            'guard_confirmed_elapsed_s':round(armed[-1]-armed[0],3)}
