"""ROS sensor_msgs/Image to PIL. No classifier is defined here."""
from __future__ import annotations
from typing import Any
from PIL import Image

def image_from_ros_msg(msg: Any) -> Image.Image:
    """Decode basic sensor_msgs/Image formats without cv_bridge. Handles row padding.

    Only for uncompressed 8-bit images. CameraInfo/TF not inferred.
    """
    specs = {'rgb8': ('RGB', 3), 'bgr8': ('RGB', 3),
             'rgba8': ('RGBA', 4), 'bgra8': ('RGBA', 4), 'mono8': ('L', 1)}
    if msg.encoding not in specs:
        raise ValueError(f'Unsupported camera encoding {msg.encoding}; use rgb8/bgr8/rgba8/bgra8/mono8')
    mode, channels = specs[msg.encoding]
    width, height, step = int(msg.width), int(msg.height), int(msg.step)
    if width <= 0 or height <= 0 or step < width*channels:
        raise ValueError('invalid image dimensions/step')
    raw = bytes(msg.data)
    if len(raw) != height * step:
        raise ValueError('ROS Image payload length does not match stride*height')
    # Keep only width*channels per row and discard padding.
    compact = b''.join(raw[r*step:r*step+width*channels] for r in range(height))
    if msg.encoding in ('bgr8', 'bgra8'):
        decoder = 'BGR' if msg.encoding == 'bgr8' else 'BGRA'
        return Image.frombytes(mode, (width, height), compact, 'raw', decoder).convert('RGB')
    return Image.frombytes(mode, (width, height), compact).convert('RGB')
