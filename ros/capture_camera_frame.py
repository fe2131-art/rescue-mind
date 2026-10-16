"""ROS2 snapshot capture utility. Run inside a sourced ROS 2 Jazzy environment."""
import argparse
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--topic', default='/camera/image_raw')
    p.add_argument('--output', default='outputs/camera.jpg')
    p.add_argument('--timeout', type=float, default=20.0)
    a=p.parse_args()
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Image
    from rescuemind.vision import image_from_ros_msg
    rclpy.init()
    class Camera(Node):
        def __init__(self):
            super().__init__('rescuemind_camera_capture')
            self.frame=None
            self.sub=self.create_subscription(Image,a.topic,self.on_image,10)
        def on_image(self,msg):
            if self.frame is None:
                self.frame=image_from_ros_msg(msg)
    node=Camera()
    try:
        import time
        start=time.monotonic()
        while rclpy.ok() and node.frame is None and time.monotonic()-start<a.timeout:
            rclpy.spin_once(node,timeout_sec=.2)
        if node.frame is None:
            raise TimeoutError('No camera image received on '+a.topic)
        path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
        node.frame.save(path,'JPEG',quality=90)
        print(path)
    finally:
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
