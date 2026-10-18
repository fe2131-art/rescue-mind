"""QoS for large image topics (ROS import deferred so offline tests stay ROS-free).

Live finding (Jazzy + Fast DDS, 4-core host under load): a best-effort
`qos_profile_sensor_data` subscriber received 10 of 102 bridged 640x480 frames,
with a 6.8 s gap, while a reliable subscriber received all of them (max gap 0.27 s).
Each ~0.9 MB image is fragmented and best-effort drops the whole sample when any
fragment is lost. The ros_gz bridge publishes RELIABLE, so a reliable, shallow
KEEP_LAST subscription is compatible and keeps freshness watchdogs truthful.
"""


def image_qos(depth: int = 2, reliability: str = 'reliable'):
    """Camera subscription QoS.  'reliable' (the default, used by every simulation run) is what the ros_gz bridge needs.
    I-26: 'best_effort' exists only for the opt-in real-robot profile (`--camera-qos best_effort` with `--clock-source system`):
    most camera drivers publish best-effort, and a Reliable subscriber never connects to them.  A best-effort subscriber
    connects to both kinds of publishers; the freshness / stationarity checks that follow are unchanged."""
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
    if reliability not in ('reliable', 'best_effort'):
        raise ValueError('image QoS must be reliable or best_effort')
    policy = ReliabilityPolicy.RELIABLE if reliability == 'reliable' else ReliabilityPolicy.BEST_EFFORT
    return QoSProfile(depth=depth, reliability=policy,
                      history=HistoryPolicy.KEEP_LAST, durability=DurabilityPolicy.VOLATILE)


def control_qos(mode: str = 'reliable', depth: int = 10):
    """I-12: QoS for the small, high-rate control topics (/rescuemind/cmd_vel_request, /rescuemind/guard_ready).

    'reliable' is the ROS default (depth 10).  'best_effort' keeps only the newest sample and never waits for
    acknowledgements; a lost sample is harmless because the guard treats a missing request as stale (zero) and
    the mission treats a missing heartbeat as 'guard not ready'.
    """
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
    if mode == 'best_effort':
        return QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST,
                          durability=DurabilityPolicy.VOLATILE)
    if mode != 'reliable':
        raise ValueError('control QoS must be reliable or best_effort')
    return QoSProfile(depth=depth, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST,
                      durability=DurabilityPolicy.VOLATILE)
