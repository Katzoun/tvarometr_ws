"""Frames the visitor's face by moving the camera in Z only.

Every step is measured from the photo pose in the goal, never from the robot's
reported position, and Z stays within min_z and max_z.
"""

import time

import rclpy
from geometry_msgs.msg import Pose, PoseArray
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from robot_control_msgs.action import ExecutePoseArray
from tvarometr_geometry.centring import Centring
from tvarometr_interfaces.action import CentreFace
from tvarometr_interfaces.srv import DetectFace


class CentringNode(Node):
    """Serves CentreFace: look, move a little, look again."""

    def __init__(self):
        super().__init__("centring_node")

        self.declare_parameter("detect_service", "/inference_node/detect_face")
        self.declare_parameter(
            "motion_action", "/robot_controller/robot_robtarget_move"
        )
        # How long to wait before reporting a missing peer at startup.
        self.declare_parameter("peer_timeout_s", 5.0)

        # In the goal's wobj; no default fits a cell.
        self.declare_parameter("min_z", 0.8)
        self.declare_parameter("max_z", 1.6)
        # Fractions of the image height.
        self.declare_parameter("target_y", 0.4)
        self.declare_parameter("tolerance", 0.05)
        # Below 1, so an error in the pixel scale undershoots instead of oscillating.
        self.declare_parameter("gain", 0.7)
        self.declare_parameter("max_step", 0.08)
        self.declare_parameter("max_steps", 15)
        self.declare_parameter("timeout_s", 30.0)
        # A face is about this tall, which is what turns pixels into metres.
        self.declare_parameter("face_height_m", 0.22)
        # Give up after this many detections in a row with nobody in front.
        self.declare_parameter("max_lost_detections", 3)
        # Includes the detector's wait for a frame taken after the robot stopped.
        self.declare_parameter("detect_timeout_s", 5.0)
        # Slow: the camera is moving to look at somebody standing close by.
        self.declare_parameter("speed", "100")
        # Work everything out and log it, but send no motion goal.
        self.declare_parameter("dry_run", False)

        self.detect_service = self._str("detect_service")
        self.motion_action = self._str("motion_action")

        self.cb_group = ReentrantCallbackGroup()
        self.detect_client = self.create_client(
            DetectFace, self.detect_service, callback_group=self.cb_group
        )
        self.motion_client = ActionClient(
            self, ExecutePoseArray, self.motion_action, callback_group=self.cb_group
        )
        self.action_server = ActionServer(
            self,
            CentreFace,
            "centring_node/centre_face",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=lambda goal_handle: CancelResponse.ACCEPT,
            callback_group=self.cb_group,
        )

        self._peer_timer = self.create_timer(
            self._double("peer_timeout_s"), self.report_peers
        )
        self.get_logger().info("Up. Checking what it can reach...")

    def _str(self, name: str) -> str:
        return self.get_parameter(name).get_parameter_value().string_value

    def _double(self, name: str) -> float:
        return self.get_parameter(name).get_parameter_value().double_value

    def _int(self, name: str) -> int:
        return self.get_parameter(name).get_parameter_value().integer_value

    def report_peers(self):
        """Says once whether both peers are there. Nothing here drives anything."""
        self._peer_timer.cancel()

        for name, ready in (
            (self.detect_service, self.detect_client.service_is_ready()),
            (self.motion_action, self.motion_client.server_is_ready()),
        ):
            if ready:
                self.get_logger().info(f"Found {name}")
            else:
                self.get_logger().warn(f"Not reachable: {name}")

    # ============= ACTION =============

    def goal_cb(self, goal_request) -> GoalResponse:
        min_z, max_z = self._double("min_z"), self._double("max_z")
        z = goal_request.photo_pose.position.z
        if min_z >= max_z:
            self.get_logger().error(
                f"Goal rejected: min_z {min_z} is not below max_z {max_z}"
            )
            return GoalResponse.REJECT
        if not min_z <= z <= max_z:
            self.get_logger().error(
                f"Goal rejected: the photo pose is at z {z:.3f}, outside [{min_z}, {max_z}]"
            )
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def execute_cb(self, goal_handle: ServerGoalHandle) -> CentreFace.Result:
        request = goal_handle.request
        tuning = Centring(
            target_y=self._double("target_y"),
            tolerance=self._double("tolerance"),
            gain=self._double("gain"),
            max_step=self._double("max_step"),
            min_z=self._double("min_z"),
            max_z=self._double("max_z"),
            face_height_m=self._double("face_height_m"),
        )
        max_steps = self._int("max_steps")
        max_lost = self._int("max_lost_detections")
        deadline = time.monotonic() + self._double("timeout_s")

        z = request.photo_pose.position.z
        # The robot already stands at the photo pose, so any frame from now counts.
        not_before = self.get_clock().now().to_msg()
        lost = 0

        for step_number in range(1, max_steps + 1):
            if goal_handle.is_cancel_requested:
                return self._cancelled(goal_handle, z, request)
            if time.monotonic() > deadline:
                return self._failed(goal_handle, z, request, "Ran out of time")

            answer = self._detect(not_before)
            if answer is None:
                lost += 1
                if lost >= max_lost:
                    return self._failed(
                        goal_handle,
                        z,
                        request,
                        f"The detector is silent ({lost} tries)",
                    )
                continue

            if not answer.success:
                # Nobody in the frame: the camera looks over everyone, so feel downwards.
                step, state = tuning.nudge(z, -1), "searching"
            elif answer.face_bbox.height == 0:
                # Their face is not in view, so steer by the top of them instead.
                blind = tuning.blind_step(
                    z, answer.person_bbox.y_offset, answer.image_height
                )
                if blind is None:
                    # The head is where a face belongs, yet no face: turned away.
                    lost += 1
                    if lost >= max_lost:
                        return self._failed(
                            goal_handle,
                            z,
                            request,
                            f"The visitor never looked at the camera ({lost} tries)",
                        )
                    continue
                step, state = blind, "looking for the face"
            else:
                step = tuning.step(
                    z,
                    answer.face_bbox.y_offset + answer.face_bbox.height / 2,
                    answer.face_bbox.height,
                    answer.image_height,
                )
                if step.centred:
                    state = "centred"
                elif step.at_limit:
                    state = "at limit"
                else:
                    state = "moving"

            lost = 0
            self._publish_feedback(goal_handle, step_number, step, state)

            if step.centred:
                return self._succeeded(
                    goal_handle,
                    z,
                    request,
                    f"Centred after {step_number - 1} move(s), {step.error_px:+.0f} px off",
                )

            if step.z != z:
                ok, message = self._move(request, step.z)
                if not ok:
                    return self._failed(goal_handle, z, request, message)
                z = step.z
                not_before = self.get_clock().now().to_msg()

            if step.at_limit:
                if state in ("searching", "looking for the face"):
                    # Nowhere left to go and still no face to analyse.
                    return self._failed(
                        goal_handle,
                        z,
                        request,
                        f"Reached z {z:.3f} without the visitor's face in view",
                    )
                # As close as the limits allow; the face is in view, so the run goes on.
                return self._succeeded(
                    goal_handle,
                    z,
                    request,
                    f"Stopped at z {z:.3f}, still {step.error_px:+.0f} px off target",
                    at_limit=True,
                )

        return self._failed(
            goal_handle, z, request, f"Not centred in {max_steps} steps"
        )

    def _publish_feedback(self, goal_handle, step_number, step, state):
        feedback = CentreFace.Feedback()
        feedback.step = step_number
        feedback.error_px = float(step.error_px)
        feedback.z = float(step.z)
        feedback.state = state
        goal_handle.publish_feedback(feedback)

    def _final_pose(self, request, z) -> Pose:
        pose = Pose()
        pose.position.x = request.photo_pose.position.x
        pose.position.y = request.photo_pose.position.y
        pose.position.z = z
        pose.orientation = request.photo_pose.orientation
        return pose

    def _result(
        self, request, z, message, success, at_limit=False
    ) -> CentreFace.Result:
        result = CentreFace.Result()
        result.success = success
        result.message = message
        result.at_limit = at_limit
        result.final_pose = self._final_pose(request, z)
        return result

    def _succeeded(self, goal_handle, z, request, message, at_limit=False):
        goal_handle.succeed()
        self.get_logger().info(message)
        return self._result(request, z, message, success=True, at_limit=at_limit)

    def _failed(self, goal_handle, z, request, message):
        goal_handle.abort()
        self.get_logger().warn(message)
        return self._result(request, z, message, success=False)

    def _cancelled(self, goal_handle, z, request):
        goal_handle.canceled()
        message = "Centring cancelled"
        self.get_logger().warn(message)
        return self._result(request, z, message, success=False)

    # ============= PEERS =============

    def _detect(self, not_before):
        """Where the visitor is, or None when the detector does not answer.

        success false means nobody is in the frame, which the loop acts on.
        """
        request = DetectFace.Request()
        request.not_before = not_before
        future = self.detect_client.call_async(request)
        response = self._wait(future, self._double("detect_timeout_s"))
        if response is None:
            self.get_logger().warn(f"{self.detect_service} did not answer")
            return None
        if not response.success:
            self.get_logger().warn(response.message)
        return response

    def _move(self, request, z) -> tuple[bool, str]:
        """One MoveL to the photo pose at the new height."""
        goal = ExecutePoseArray.Goal()
        goal.motion_command = "MoveL"
        goal.speed = self._str("speed")
        goal.tool = request.tool
        goal.wobj = request.wobj
        path = PoseArray()
        path.header.stamp = self.get_clock().now().to_msg()
        path.poses = [self._final_pose(request, z)]
        goal.path = path

        if self.get_parameter("dry_run").get_parameter_value().bool_value:
            self.get_logger().info(f"dry_run: would move to z {z:.3f}")
            return True, ""

        send = self.motion_client.send_goal_async(goal)
        motion = self._wait(send, self._double("detect_timeout_s"))
        if motion is None:
            return False, f"{self.motion_action} did not answer"
        if not motion.accepted:
            return False, "The driver refused the move"

        outcome = self._wait(motion.get_result_async(), self._double("timeout_s"))
        if outcome is None:
            motion.cancel_goal_async()
            return False, "The robot did not report arriving"
        if not outcome.result.success:
            return False, f"Move failed: {outcome.result.message}"
        return True, ""

    @staticmethod
    def _wait(future, timeout_s):
        """The future's result, or None if it does not arrive within the timeout.

        Blocks this thread only - the executor is what completes the future.
        """
        deadline = time.monotonic() + timeout_s
        while not future.done():
            if time.monotonic() > deadline:
                return None
            time.sleep(0.01)
        return future.result()


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = CentringNode()
        # The loop waits on a service and an action inside a callback.
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if executor:
            executor.shutdown(timeout_sec=5)
        if node:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
