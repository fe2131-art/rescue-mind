"""Offline deterministic CLOSED-LOOP contract experiment (NOT Gazebo or real AI).

Combines the real WaypointController, VelocityRelay (same core used in ROS),
and ideal unicycle integration. Sensor messages and model decisions are scripted.
Purpose: catch integration regressions that isolated unit tests miss.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import pi, isfinite
from types import SimpleNamespace as N
from .waypoint import Pose2, WaypointController, integrate
from .velocity_relay import VelocityRelay

DT = 0.1
GOALS = ((1.18, 1.13), (2.15, -1.12))


def stamp(t):
    ns = max(1, round((t + 1) * 1_000_000_000))
    return N(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)


def fake_odom(pose, t):
    from math import sin,cos
    return N(header=N(stamp=stamp(t), frame_id='odom'), child_frame_id='base_link',
             pose=N(pose=N(position=N(x=pose.x, y=pose.y, z=0.0),
                           orientation=N(x=0.0, y=0.0, z=sin(pose.yaw/2), w=cos(pose.yaw/2)))))


def fake_camera(t):
    return N(header=N(stamp=stamp(t)))


def fake_scan(distance=float('inf')):
    return N(ranges=[distance]*360, angle_min=-pi, angle_increment=2*pi/360,
             range_min=.08, range_max=10.0)


@dataclass(frozen=True)
class TwinResult:
    kind: str
    scenario: str
    mission_completed: bool
    terminal_reason: str
    station_reached: bool
    shelter_reached: bool
    simulated_ai_calls: int
    guard_emitted_nonzero: int
    guard_emitted_zero: int
    stop_delay_s: float | None
    last_position: tuple[float,float,float]
    elapsed_s: float
    trace: list[dict]

    def as_dict(self):
        return asdict(self)


def simulate(scenario='nominal', *, dt=DT, duration_s=100.0):
    """Returns an audit receipt of a scripted closed-loop experiment.

    * nominal: two waypoints, scripted allow at supply
    * ai_denied: stop at supply (scripted deny, NOT Jev/Qwen model call)
    * lidar_block: after 2 seconds send a 0.20 m obstacle
    * command_loss: stop publishing commands after 2 seconds
    * camera_freeze: stop camera timestamps after 2 seconds
    * odom_freeze: stop odometry updates after 2 seconds

    A stop does not simulate brake inertia; this is NOT a Gazebo safety test.
    """
    allowed=('nominal','ai_denied','lidar_block','command_loss','camera_freeze','odom_freeze')
    if scenario not in allowed:
        raise ValueError('unsupported scenario')
    if not (.02 <= dt <= .20 and isfinite(dt) and 4 < duration_s <= 300):
        raise ValueError('invalid integration settings')
    pose=Pose2(0.,0.,0.)
    ctl=WaypointController()
    relay=VelocityRelay(started_at=0.)
    stage=0
    station_reached=False
    shelter_reached=False
    simulated_ai_calls=0
    permitted=False
    traces=[]
    nonzero=0
    zero=0
    guard_reason='not_started'
    activation_time=None
    stopped_at=None
    last_motion=0.0
    steps=int(duration_s/dt)
    for k in range(1,steps+1):
        now=k*dt
        if scenario != 'odom_freeze' or now <= 2.0:
            relay.odometry(now,fake_odom(pose,now))
        if scenario != 'camera_freeze' or now <= 2.0:
            relay.camera_frame(fake_camera(now),now)
        laser_dist=.20 if scenario == 'lidar_block' and now >= 2.0 else float('inf')
        relay.laser_scan(fake_scan(laser_dist),now)
        if not station_reached:
            instruction=ctl.command(pose,GOALS[0])
            if instruction.arrived:
                station_reached=True
                simulated_ai_calls+=1
                permitted=(scenario!='ai_denied') # scripted fixture, not model inference
                instruction=ctl.command(pose,GOALS[0])
        elif not permitted:
            instruction=ctl.command(pose,GOALS[0])
        else:
            instruction=ctl.command(pose,GOALS[1])
            if instruction.arrived:
                shelter_reached=True
        req_linear,req_angular=(0.,0.) if (station_reached and not permitted) or shelter_reached else (instruction.linear,instruction.angular)
        if scenario != 'command_loss' or now <= 2.0:
            relay.request(req_linear,req_angular,now)
        decision=relay.decide(now)
        # The motor receives the ACTUAL guarded request, not the raw planner request.
        if abs(decision.linear)>1e-8 or abs(decision.angular)>1e-8:
            nonzero+=1
            last_motion=now
        else:
            zero+=1
        pose=integrate(pose, type(instruction)(decision.linear,decision.angular), dt)
        guard_reason=decision.reason
        if k%10==0 or not decision.ready or (station_reached and simulated_ai_calls==1 and not permitted):
            traces.append({'t':round(now,3),'x':round(pose.x,4),'y':round(pose.y,4),
                           'stage':('station' if not station_reached else 'shelter'),
                           'ai_fixture':('DENY' if station_reached and not permitted else ('ALLOW' if station_reached else 'NOT_CALLED')),
                           'command':[round(decision.linear,4),round(decision.angular,4)],
                           'guard_reason':decision.reason})
        if shelter_reached:
            stopped_at=now
            break
        if scenario == 'ai_denied' and station_reached:
            stopped_at=now
            break
        if not decision.ready:
            stopped_at=now
            break
    mission_completed=bool(shelter_reached and permitted)
    if mission_completed:
        terminal='arrived_shelter_after_scripted_allow'
    elif scenario=='ai_denied' and station_reached:
        terminal='scripted_ai_denied_at_station'
    elif not relay.ready(stopped_at if stopped_at else steps*dt):
        terminal='guard_latched:'+guard_reason
    else:
        terminal='timeout_or_incomplete'
    # For fault injection, measure delay from defect activation t=2s to zero output.
    fault_scenarios=('lidar_block','command_loss','camera_freeze','odom_freeze')
    stop_delay=(max(0.,(stopped_at or duration_s)-2.0) if scenario in fault_scenarios else None)
    return TwinResult('SCRIPTED_CLOSED_LOOP_NOT_REAL_AI_NOT_GAZEBO',scenario,
                      mission_completed,terminal,station_reached,shelter_reached,
                      simulated_ai_calls,nonzero,zero,
                      round(stop_delay,3) if stop_delay is not None else None,
                      (round(pose.x,4),round(pose.y,4),round(pose.yaw,4)),
                      round(stopped_at or duration_s,3),traces)
