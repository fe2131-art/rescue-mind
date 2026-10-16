# v2.7 adversarial camera-acquisition experiments — OFFLINE ONLY

Input = generated 320x240 `sensor_msgs/Image`-like payloads with synthetic ROS acquisition stamps. The same *production* `CheckpointAcquisitionGate` and decoder are exercised.

Good examples: textured pattern, padded rows; both require 2 distinct post-settle stamps separated by >=0.15 s. Refusal examples: blacked out, whiteout, uniform mid-gray, near-black, truncated payload, unsupported encoding, stamp regression, queued old sample, pre-dwell frame, duplicate stamp, too-short callback interval, missing second frame.

Run `python3 scripts/v27_acquisition_campaign.py`; artifact `verification/v27/synthetic_camera_campaign.json` logs every expected and observed outcome. This is an **adversarial interface test**, not recognition accuracy. No genuine camera image is packaged. The `checkpoint_image_quality_verified` receipt plus `image_sha256` matches the saved JPEG before any result is called a real-world success. The recorder runs separately but is not cryptographically authenticated.

Failure taxonomy: `CAMERA_ACQUISITION_FAILURE` = inability to get a usable camera frame, not `AI_DENIAL_CORRECT`. `AI_DENIAL_CORRECT` requires actual Jev and Qwen decisions + independent stationary odometry verification. `API_FAILURE` is not a model recognition error and must be counted separately.

Limitations: simple luminance histogram cannot test object identity, occlusion, depth, motion blur, saturation color discrimination, lens obstruction with textured overlay, or adversarial image manipulation. Rejecting a flat-frame may make the empty-shelf scene unscorable. Record such trials as acquisition failures, not correct expected denials. Adjust thresholds **only before** an experiment run, with versioned settings and preregistration.
