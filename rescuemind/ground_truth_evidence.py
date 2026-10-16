"""Audit a run against Gazebo's own ground-truth pose, not the controller's odometry.

Why this exists: the v3.2 handoff world declared the wheel joint axis in the
rolled wheel frame, so the wheels spun about the vertical axis.  DiffDrive's
wheel odometry still reported 1.50 m of forward travel while Gazebo's true pose
showed the chassis sliding 0.75 m sideways and pitching ~40 deg.  Every audit fed
by /odom would have accepted that run.  A ground-truth stream from the simulator
(OdometryPublisher on the model pose, bridged as /ground_truth/odom) closes the gap:
arrival, stationarity during AI denial, chassis attitude and odometry drift are
checked against what the physics engine actually did.
"""
from __future__ import annotations
import bisect
import json
import math
from pathlib import Path


class GroundTruthError(ValueError):
    pass


def _rows(path):
    gt, odom = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if r.get('kind') == 'ground_truth':
            gt.append(r)
        elif r.get('kind') == 'odom':
            odom.append(r)
    if len(gt) < 20:
        raise GroundTruthError('too few ground-truth samples (is /ground_truth/odom bridged?)')
    for rows in (gt, odom):
        rows.sort(key=lambda r: r['ros_stamp_ns'])
    return gt, odom


def _tilt_deg(r):
    qx, qy, qz, qw = r['qx'], r['qy'], r['qz'], r['qw']
    # angle between body z axis and world z axis
    zz = 1 - 2 * (qx * qx + qy * qy)
    return math.degrees(math.acos(max(-1.0, min(1.0, zz))))


def _odom_drift(gt, odom):
    """Max planar distance between wheel odometry and truth at matching sim stamps."""
    if not odom:
        return None
    stamps = [r['ros_stamp_ns'] for r in gt]
    worst = 0.0
    for o in odom[::5]:
        i = bisect.bisect_left(stamps, o['ros_stamp_ns'])
        cand = [j for j in (i - 1, i) if 0 <= j < len(gt)]
        j = min(cand, key=lambda k: abs(stamps[k] - o['ros_stamp_ns']))
        if abs(stamps[j] - o['ros_stamp_ns']) > 100_000_000:
            continue
        worst = max(worst, math.hypot(o['x'] - gt[j]['x'], o['y'] - gt[j]['y']))
    return worst


def audit_ground_truth(path, *, station, shelter, expect_arrival: bool,
                       tolerance=0.34, max_tilt_deg=8.0, max_drift_m=0.25, look_around_m: float = 0.0):
    gt, odom = _rows(path)
    dist = lambda r, g: math.hypot(r['x'] - g[0], r['y'] - g[1])
    start = gt[0]
    if math.hypot(start['x'], start['y']) > 0.3:
        raise GroundTruthError('true start pose not at world origin')
    tilt = max(_tilt_deg(r) for r in gt)
    if tilt > max_tilt_deg:
        raise GroundTruthError(f'chassis tipped {tilt:.1f} deg (physics fault)')
    i_station = next((i for i, r in enumerate(gt) if dist(r, station) <= tolerance), None)
    if i_station is None:
        raise GroundTruthError('true pose never reached the supply station')
    path_m = sum(math.hypot(b['x'] - a['x'], b['y'] - a['y']) for a, b in zip(gt, gt[1:]))
    drift = _odom_drift(gt, odom)
    if drift is not None and drift > max_drift_m:
        raise GroundTruthError(f'wheel odometry diverged {drift:.2f} m from ground truth')
    after = gt[i_station:]
    closest_shelter = min(dist(r, shelter) for r in after)
    report = {'scope': 'GAZEBO_GROUND_TRUTH_MODEL_POSE', 'samples': len(gt),
              'true_path_length_m': round(path_m, 3), 'max_tilt_deg': round(tilt, 2),
              'max_odom_vs_truth_m': None if drift is None else round(drift, 3),
              'closest_true_distance_to_shelter_m': round(closest_shelter, 3),
              'final_true_xy': [round(gt[-1]['x'], 3), round(gt[-1]['y'], 3)]}
    if expect_arrival:
        if closest_shelter > tolerance:
            raise GroundTruthError('true pose never reached the shelter after the station')
        report['pass'] = True
        return report
    # Denial: after reaching the station the chassis must not head for the shelter.
    station_xy = (gt[i_station]['x'], gt[i_station]['y'])
    excursion = max(math.hypot(r['x'] - station_xy[0], r['y'] - station_xy[1]) for r in after)
    if excursion > 0.45 + look_around_m or closest_shelter < 1.0:   # I-14: side views widen the dwell area
        raise GroundTruthError(f'robot left the station after denial (excursion {excursion:.2f} m)')
    report.update(max_excursion_after_station_m=round(excursion, 3), pass_=True)
    report['pass'] = report.pop('pass_')
    return report
