"""Frames a face in the camera before the analysis pass runs.

The camera rides on the flange, so moving the arm moves the view: a child's
face sits low in the frame, and walking the camera down to it is what gets
RunInference a picture worth analysing.

The control loop is not written yet. What is here is the wiring - the two
things this node talks to - so that a missing piece says so on startup instead
of halfway through a run.
"""

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from robot_control_msgs.action import ExecutePoseArray

from tvarometr_interfaces.srv import DetectFace


class CentringNode(Node):
    """Holds the clients the centring loop will drive."""

    def __init__(self):
        super().__init__('centring_node')

        # Named rather than hard-coded: the inference node answers in the vision
        # container and the driver in its own, and either can be remapped.
        self.declare_parameter('detect_service', '/inference_node/detect_face')
        self.declare_parameter('motion_action', '/robot_controller/robot_robtarget_move')
        # How long to wait on startup before saying a peer is missing. Long
        # enough that the usual start-everything-at-once is not reported as a
        # fault, short enough to still be a startup message.
        self.declare_parameter('peer_timeout_s', 5.0)

        self.detect_service = self.get_parameter('detect_service').value
        self.motion_action = self.get_parameter('motion_action').value

        self.detect_client = self.create_client(DetectFace, self.detect_service)
        # Cartesian, because the correction is a shift of the camera and not an
        # angle on any one axis.
        self.motion_client = ActionClient(self, ExecutePoseArray, self.motion_action)

        timeout = self.get_parameter('peer_timeout_s').value
        self._peer_timer = self.create_timer(timeout, self.report_peers)
        self.get_logger().info('Up. Checking what it can reach...')

    def report_peers(self):
        """Says once whether both peers are there. Nothing here drives anything."""
        self._peer_timer.cancel()

        for name, ready in (
            (self.detect_service, self.detect_client.service_is_ready()),
            (self.motion_action, self.motion_client.server_is_ready()),
        ):
            if ready:
                self.get_logger().info(f'Found {name}')
            else:
                self.get_logger().warn(f'Not reachable: {name}')


def main(args=None):
    rclpy.init(args=args)
    node = CentringNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
