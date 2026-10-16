"""Conservative, ROS-independent checkpoint image acceptance gate.

After the robot aims and proves stationarity, require TWO distinct new camera
acquisitions before accepting an image for Jev + Qwen. Reject broken payloads,
severe blackout/whiteout and flat frames. This is a technical acquisition test,
NOT an object detector or a substitute for real Gazebo image inspection.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from PIL import Image
from .frame_freshness import frame_stamp_ns
from .vision import image_from_ros_msg

class AcquisitionRejected(ValueError):
    pass


def measure_quality(image: Image.Image) -> dict:
    """Quantile and clipping metrics on a deterministic downsampled luminance image."""
    if not isinstance(image, Image.Image) or not (320 <= image.width <= 4096 and 240 <= image.height <= 4096):
        raise AcquisitionRejected('invalid_image_resolution')
    # PIL histogram avoids numpy / cv_bridge dependencies on ROS Jazzy venvs.
    gray=image.convert('L').resize((160,120),Image.Resampling.BOX)
    h=gray.histogram()
    n=sum(h)
    def quantile(q):
        threshold=n*q
        s=0
        for idx,count in enumerate(h):
            s+=count
            if s>=threshold:
                return idx
        return 255
    low,high=quantile(.01),quantile(.99)
    dark=sum(h[:10])/n
    bright=sum(h[246:])/n
    reasons=[]
    if dark >= .99:reasons.append('camera_blackout')
    if bright >= .99:reasons.append('camera_whiteout')
    if high-low < 4:reasons.append('camera_flat_frame')
    return {'width':image.width,'height':image.height,'p01_luma':low,'p99_luma':high,
            'dark_fraction':round(dark,5),'bright_fraction':round(bright,5),
            'quality_ok':not reasons,'reasons':reasons,
            'scope':'gross_exposure_sanity_not_semantic_recognition_or_blur_calibration'}


@dataclass
class CheckpointAcquisitionGate:
    """Two consecutive valid captures after the stationary-camera dwell.

    Invalid post-dwell frames cause a hard failure; no silent cherry-picking
    from retries. Duplicate/stale frame stamps never count as another capture.
    """
    previous_stamp_ns:int
    earliest_wall_s:float
    min_gap_s:float=.15
    accepted:list[tuple[int,float,dict]]=field(default_factory=list)
    frame:Image.Image|None=None

    def __post_init__(self):
        if type(self.previous_stamp_ns) is not int or self.previous_stamp_ns<=0:
            raise AcquisitionRejected('missing_pre_dwell_camera_stamp')
        if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)
                   for x in (self.earliest_wall_s,self.min_gap_s)) or self.min_gap_s<.10:
            raise AcquisitionRejected('bad_capture_time_window')

    def observe(self, msg, callback_wall_s:float)->bool:
        if self.frame is not None:return True
        if not isinstance(callback_wall_s,(int,float)) or not math.isfinite(callback_wall_s):
            raise AcquisitionRejected('bad_frame_receive_time')
        if callback_wall_s<=self.earliest_wall_s:
            return False
        stamp=frame_stamp_ns(msg)
        if stamp is None or stamp<=self.previous_stamp_ns:
            # Frames queued before the locked-stationary window must not pass.
            if stamp is None:raise AcquisitionRejected('invalid_checkpoint_stamp')
            return False
        if self.accepted:
            if stamp<=self.accepted[-1][0]:
                if stamp<self.accepted[-1][0]:raise AcquisitionRejected('camera_stamp_regressed')
                return False
            if callback_wall_s<=self.accepted[-1][1]:
                raise AcquisitionRejected('camera_callback_time_regressed')
            if callback_wall_s-self.accepted[-1][1]<self.min_gap_s:
                return False
        try:
            # Reject impossible or oversized camera payloads BEFORE decoding.
            # The ROS bridge already allocated the message, but this bounds
            # the extra PIL conversion/copy work done inside the mission.
            if not (320 <= int(msg.width) <= 4096 and 240 <= int(msg.height) <= 4096):
                raise AcquisitionRejected('invalid_checkpoint_image_dimensions')
            if int(msg.step) < int(msg.width) or int(msg.step)>int(msg.width)*4+4096:
                raise AcquisitionRejected('implausible_checkpoint_row_stride')
            if len(msg.data)>80_000_000:
                raise AcquisitionRejected('oversized_checkpoint_image_payload')
            rgb=image_from_ros_msg(msg)
            q=measure_quality(rgb)
        except (AttributeError,TypeError,ValueError,OverflowError,OSError,MemoryError) as exc:
            if isinstance(exc,AcquisitionRejected):raise
            raise AcquisitionRejected('malformed_checkpoint_image: '+str(exc)) from exc
        if not q['quality_ok']:
            raise AcquisitionRejected('poor_checkpoint_image_quality: '+','.join(q['reasons']))
        self.accepted.append((stamp,callback_wall_s,q))
        if len(self.accepted)>=2:
            self.frame=rgb
        return self.frame is not None

    def report(self)->dict:
        if self.frame is None or len(self.accepted)<2:
            raise AcquisitionRejected('two_fresh_quality_frames_not_proven')
        return {'distinct_frames':len(self.accepted),'ros_stamps_ns':[r[0] for r in self.accepted],
                'capture_gap_wall_s':round(self.accepted[1][1]-self.accepted[0][1],4),
                'image_quality':self.accepted[-1][2],
                'selection':'second_consecutive_valid_post_stationarity_frame'}
