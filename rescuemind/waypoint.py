"""Research-only 2-D unicycle waypoint follower; pure Python / independently testable.

Uses odometry as reported by Gazebo /odom. Stopping/turning is reactive and
NOT an obstacle-avoiding global planner. A watchdog is mandatory on live ROS.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, pi, sin


def wrap(angle: float) -> float:
    return atan2(sin(angle), cos(angle))


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    vals = (x, y, z, w)
    if not all(isfinite(v) for v in vals):
        raise ValueError('non-finite quaternion')
    norm = sum(v*v for v in vals)
    if not .9 < norm < 1.1:
        raise ValueError('bad quaternion norm')
    return atan2(2*(w*z+x*y), 1-2*(y*y+z*z))

@dataclass(frozen=True)
class Pose2:
    x: float
    y: float
    yaw: float

    def __post_init__(self):
        if not all(isfinite(t) for t in (self.x,self.y,self.yaw)):
            raise ValueError('non-finite pose')

@dataclass(frozen=True)
class MotionCommand:
    linear: float
    angular: float
    arrived: bool = False

class WaypointController:
    """Go-to-goal with turn-in-place when heading error is large.

    No dynamic replanning and no obstacle avoidance. Live deployment requires
    a separate watchdog and an actual LiDAR feed.
    """
    def __init__(self, speed=.19, turn_speed=.75, tolerance=.23, turn_deadband=.38):
        if not (0 < speed <= .35 and 0 < turn_speed <= 1.5 and 0 < tolerance <= .5 and
                0 < turn_deadband < 1.5):
            raise ValueError('invalid controller config')
        self.speed=speed; self.turn_speed=turn_speed
        self.tolerance=tolerance; self.turn_deadband=turn_deadband

    def command(self, pose: Pose2, goal: tuple[float,float]) -> MotionCommand:
        gx,gy=goal
        if not all(isfinite(v) for v in goal):
            raise ValueError('invalid goal')
        dx,dy=gx-pose.x,gy-pose.y
        dist=hypot(dx,dy)
        if dist <= self.tolerance:
            return MotionCommand(0.,0.,True)
        err=wrap(atan2(dy,dx)-pose.yaw)
        angular=max(-self.turn_speed,min(self.turn_speed,2.0*err))
        if abs(err) > self.turn_deadband:
            return MotionCommand(0.,angular)
        forward=min(self.speed, max(.06,.7*dist)) * max(0.,cos(err))
        return MotionCommand(forward,angular)


def integrate(pose: Pose2, cmd: MotionCommand, dt: float) -> Pose2:
    """Idealized unicycle motion, independent of Gazebo (tests only)."""
    if not 0 < dt <= .2:
        raise ValueError('time step outside integration limits')
    yaw_mid=pose.yaw + cmd.angular*dt/2
    return Pose2(pose.x+cmd.linear*cos(yaw_mid)*dt,
                 pose.y+cmd.linear*sin(yaw_mid)*dt,wrap(pose.yaw+cmd.angular*dt))


def simulate_route(goals, *, dt=.08, max_steps=22000):
    """Math-only integration regression. Cannot count as a robot video."""
    pose=Pose2(0.,0.,0.)
    ctl=WaypointController()
    trace=[]
    for i,g in enumerate(goals):
        reached=False
        for k in range(max_steps):
            cmd=ctl.command(pose,g)
            if cmd.arrived:
                reached=True
                break
            pose=integrate(pose,cmd,dt)
            if k%12==0:
                trace.append({'stage':i,'x':round(pose.x,4),'y':round(pose.y,4),'yaw':round(pose.yaw,4)})
        if not reached:
            raise TimeoutError(f'unicycle regression did not reach waypoint {i}')
    return {'kind':'ideal_kinematic_regression_not_gazebo','arrived':True,
            'final':[round(pose.x,4),round(pose.y,4),round(pose.yaw,4)],
            'steps':len(trace),'trace':trace}
