"""The webcam's own JPEGs on image_raw/compressed, never decoded here.

Replaces usb_cam, whose raw MJPEG mode segfaults in 0.8.1.
"""

import threading
import time

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


class CameraNode(Node):
    def __init__(self):
        super().__init__("camera")
        self.declare_parameter("video_device", "/dev/video0")
        self.declare_parameter("image_width", 1920)
        self.declare_parameter("image_height", 1080)
        self.declare_parameter("framerate", 30.0)
        self.declare_parameter("frame_id", "camera")

        # Reliable so rqt_image_view matches too; depth 1, only the newest frame counts.
        self.publisher = self.create_publisher(
            CompressedImage, "image_raw/compressed", 1
        )
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _param(self, name):
        return self.get_parameter(name).get_parameter_value()

    def _open(self):
        device = self._param("video_device").string_value
        capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._param("image_width").integer_value)
        capture.set(
            cv2.CAP_PROP_FRAME_HEIGHT, self._param("image_height").integer_value
        )
        capture.set(cv2.CAP_PROP_FPS, self._param("framerate").double_value)
        # Hands back each frame as the camera's JPEG instead of decoding it.
        capture.set(cv2.CAP_PROP_CONVERT_RGB, 0)

        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode()
        if not capture.isOpened() or fourcc != "MJPG":
            self.get_logger().error(
                f"Cannot stream MJPG from {device}", throttle_duration_sec=10.0
            )
            capture.release()
            return None
        self.get_logger().info(
            f"Streaming {device}: {capture.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}x"
            f"{capture.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f} MJPG at "
            f"{capture.get(cv2.CAP_PROP_FPS):.0f} fps"
        )
        return capture

    def _capture_loop(self):
        frame_id = self._param("frame_id").string_value
        capture = None
        while not self._stop.is_set():
            if capture is None:
                capture = self._open()
                if capture is None:
                    time.sleep(1.0)
                    continue

            ok, jpeg = capture.read()
            if not ok:
                self.get_logger().warning("Lost the camera, reopening it")
                capture.release()
                capture = None
                time.sleep(1.0)
                continue

            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = frame_id
            msg.format = "jpeg"
            msg.data.frombytes(jpeg.tobytes())
            self.publisher.publish(msg)

        if capture is not None:
            capture.release()

    def destroy_node(self):
        self._stop.set()
        self._thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = CameraNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
