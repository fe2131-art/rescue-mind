# RescueMind runtime: Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic + CUDA PyTorch (V100 FP16).
# Lets an Ubuntu 22.04 GPU host run the Jazzy/Harmonic stack without sudo (docker group only).
FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-ros-gz \
        ros-jazzy-rosbag2 \
        ros-jazzy-rosbag2-storage-mcap \
        python3-venv python3-pip python3-pil python3-yaml python3-numpy \
        ffmpeg xvfb x11-utils xdotool mesa-utils libegl1 libgl1 libglx-mesa0 \
        fonts-noto-cjk fonts-ipaexfont curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Isolated venv that still sees apt-installed rclpy (system site packages).
RUN python3 -m venv --system-site-packages /opt/rescuemind-venv \
    && /opt/rescuemind-venv/bin/pip install -U 'pip<26' \
    && /opt/rescuemind-venv/bin/pip install 'torch==2.5.1' 'torchvision==0.20.1' \
         --index-url https://download.pytorch.org/whl/cu121 \
    && /opt/rescuemind-venv/bin/pip install \
         'transformers==4.53.3' 'accelerate==1.9.0' 'huggingface_hub==0.33.4' \
         'num2words>=0.5' 'safetensors>=0.4' 'scikit-learn>=1.3,<2' 'Pillow>=9' \
         'matplotlib>=3.8' 'opencv-python-headless>=4.9' 'reportlab>=4.0'

ENV RESCUEMIND_VENV=/opt/rescuemind-venv \
    NVIDIA_DRIVER_CAPABILITIES=all \
    QT_X11_NO_MITSHM=1

COPY entrypoint.sh /usr/local/bin/rescuemind-entrypoint
RUN chmod +x /usr/local/bin/rescuemind-entrypoint
ENTRYPOINT ["/usr/local/bin/rescuemind-entrypoint"]
CMD ["bash"]
