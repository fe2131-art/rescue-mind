"""Camera degradations for the sensor-realism study R (experiments/PREREGISTRATION_R.md).

Gazebo renders are noise-free, perfectly focused and well exposed; a real robot camera is not.  These six families
follow the spirit of ImageNet-C (Hendrycks & Dietterich, ICLR 2019) but use pixel parameters chosen for our
640x480 checkpoint camera, fixed before any result was seen.  Every function is deterministic given (image, seed).
"""
from __future__ import annotations
import io
import numpy as np
from PIL import Image

# family -> {severity: parameter}; M = moderate (plausible on a working camera), S = severe (a bad but usable frame)
PARAMS = {
    'gaussian_noise': {'M': 0.04, 'S': 0.10},     # sigma on [0, 1] intensities (sensor read noise, high gain)
    'motion_blur': {'M': 9, 'S': 21},             # horizontal line-kernel length in px (vibration / residual motion)
    'defocus_blur': {'M': 2, 'S': 5},             # disk radius in px (focus error)
    'underexposure': {'M': 0.45, 'S': 0.25},      # intensity gain, then sensor noise sigma 0.01 (dim scene)
    'overexposure': {'M': 1.6, 'S': 2.2},         # intensity gain with clipping (bright scene, auto-exposure lag)
    'jpeg': {'M': 20, 'S': 8},                    # JPEG quality (bandwidth-limited image link)
}
CONDITIONS = [f'{f}_{s}' for f in PARAMS for s in ('M', 'S')]


def _disk(r: int) -> np.ndarray:
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    k = (x * x + y * y <= r * r + 0.5).astype(np.float32)
    return k / k.sum()


def _convolve(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Same-size 2-D convolution per channel with edge padding (FFT-free; kernels are small)."""
    kh, kw = k.shape
    ph, pw = kh // 2, kw // 2
    p = np.pad(a, ((ph, ph), (pw, pw), (0, 0)), mode='edge')
    out = np.zeros_like(a)
    for i in range(kh):
        for j in range(kw):
            if k[i, j]:
                out += k[i, j] * p[i:i + a.shape[0], j:j + a.shape[1]]
    return out


def corrupt(image: Image.Image, condition: str, seed: int = 0) -> Image.Image:
    family, sev = condition.rsplit('_', 1)
    v = PARAMS[family][sev]
    rng = np.random.default_rng(seed)
    a = np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0
    if family == 'gaussian_noise':
        a = a + rng.normal(0, v, a.shape)
    elif family == 'motion_blur':
        a = _convolve(a, np.full((1, v), 1.0 / v, np.float32))
    elif family == 'defocus_blur':
        a = _convolve(a, _disk(v))
    elif family == 'underexposure':
        a = a * v + rng.normal(0, 0.01, a.shape)
    elif family == 'overexposure':
        a = a * v
    elif family == 'jpeg':
        buf = io.BytesIO()
        image.convert('RGB').save(buf, 'JPEG', quality=v)
        return Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
    else:
        raise ValueError(condition)
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def corrupt_jpeg_bytes(image: Image.Image, condition: str, seed: int = 0) -> bytes:
    """What the robot would send to the VLM: the corrupted frame, saved like a checkpoint image (JPEG q90)."""
    out = corrupt(image, condition, seed)
    if condition.startswith('jpeg_'):
        buf = io.BytesIO(); out.save(buf, 'PNG'); return buf.getvalue()   # keep the low-quality JPEG artefacts as is
    buf = io.BytesIO()
    out.save(buf, 'JPEG', quality=90)
    return buf.getvalue()

