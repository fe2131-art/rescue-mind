"""QoS for large image topics (ROS import deferred so offline tests stay ROS-free).

Live finding (Jazzy + Fast DDS, 4-core host under load): a best-effort
`qos_profile_sensor_data` subscriber received 10 of 102 bridged 640x480 frames,
with a 6.8 s gap, while a reliable subscriber received all of them (max gap 0.27 s).
Each ~0.9 MB image is fragmented and best-effort drops the whole sample when any
fragment is lost. The ros_gz bridge publishes RELIABLE, so a reliable, shallow
KEEP_LAST subscription is compatible and keeps freshness watchdogs truthful.
"""


def image_qos(depth: int = 2):
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
    return QoSProfile(depth=depth, reliability=ReliabilityPolicy.RELIABLE,
                      history=HistoryPolicy.KEEP_LAST, durability=DurabilityPolicy.VOLATILE)
