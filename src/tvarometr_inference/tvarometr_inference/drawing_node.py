#!/usr/bin/env python3
"""Turns a face analysis into the path the robot draws on the whiteboard.

Splitting this out of the master node means the drawing can be produced and
looked at without a robot, a camera or the state machine - feed it a
FaceAttributes message and you get the geometry back.

The Czech wording lives here rather than in the vision node: FaceAttributes
carries the models' own English labels, and this is the point where the text that
actually gets written is decided.
"""

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn

from geometry_msgs.msg import Pose, PoseArray

from tvarometr_interfaces.action import GenerateDrawing
from tvarometr_inference.path_generator import generate_path

EMOTION_CS = {
    "anger": "nastvany",
    "disgust": "znechuceny",
    "fear": "vydeseny",
    "happiness": "stastny",
    "sadness": "smutny",
    "surprise": "prekvapeny",
    "neutral": "neutralni",
}

GENDER_CS = {"male": "muz", "female": "zena"}


class DrawingNode(LifecycleNode):

    def __init__(self):
        super().__init__('drawing_node')
        self.NODE_NAME = 'drawing_node'
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()

        self.declare_parameter('letter_height', 60.0)
        self.declare_parameter('letter_spacing', 10.0)
        self.declare_parameter('space_factor', 1.3)
        self.declare_parameter('line_spacing', 1.5)

        # The pen orientation every point is written with. Default is the
        # quaternion the master node has always sent - ABB [0,1,0,0] in w,x,y,z,
        # which is x,y,z,w = 1,0,0,0 the ROS way round.
        self.declare_parameter('pen_orientation', [1.0, 0.0, 0.0, 0.0])

        self._active = False
        self.action_server = ActionServer(
            self,
            GenerateDrawing,
            f'{self.NODE_NAME}/generate_drawing',
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=lambda goal_handle: CancelResponse.ACCEPT,
            callback_group=self.cb_group,
        )

        self.logger.info('Unconfigured - configure and activate to accept goals')

    # ============= LIFECYCLE =============

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.logger.info('Configured')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._active = True
        self.logger.info('Active - accepting drawing goals')
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return TransitionCallbackReturn.SUCCESS

    # ============= ACTION =============

    def goal_cb(self, goal_request) -> GoalResponse:
        if not self._active:
            self.logger.error('Goal rejected: node is not active')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def compose_text(self, attributes) -> str:
        gender = GENDER_CS.get(attributes.gender, attributes.gender)
        emotion = EMOTION_CS.get(attributes.emotion, attributes.emotion)
        return (f"Vek:       {attributes.age},\n"
                f"Pohlavi:   {gender},\n"
                f"Emoce:   {emotion}")

    def execute_cb(self, goal_handle: ServerGoalHandle) -> GenerateDrawing.Result:
        result = GenerateDrawing.Result()
        feedback = GenerateDrawing.Feedback()

        text = self.compose_text(goal_handle.request.attributes)
        self.logger.info(f'Generating a drawing for: {text!r}')
        feedback.status = 'generating'
        goal_handle.publish_feedback(feedback)

        try:
            points = generate_path(
                text,
                letter_height=self.get_parameter('letter_height').value,
                letter_spacing=self.get_parameter('letter_spacing').value,
                space_factor=self.get_parameter('space_factor').value,
                line_spacing=self.get_parameter('line_spacing').value,
            )
        except Exception as e:
            goal_handle.abort()
            result.success = False
            result.message = f'Path generation failed: {e}'
            self.logger.error(result.message)
            return result

        if not points:
            goal_handle.abort()
            result.success = False
            result.message = 'Path generation produced no points'
            self.logger.error(result.message)
            return result

        qx, qy, qz, qw = self.get_parameter('pen_orientation').value
        path = PoseArray()
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y, z in points:
            pose = Pose()
            pose.position.x, pose.position.y, pose.position.z = float(x), float(y), float(z)
            pose.orientation.x, pose.orientation.y = qx, qy
            pose.orientation.z, pose.orientation.w = qz, qw
            path.poses.append(pose)

        # Nothing is appended to park the robot afterwards - moving away from the
        # board is the RAPID routine's business, not part of the text.
        goal_handle.succeed()
        result.success = True
        result.message = f'{len(path.poses)} points for {len(text.splitlines())} lines'
        result.path = path
        feedback.points_generated = len(path.poses)
        goal_handle.publish_feedback(feedback)
        self.logger.info(result.message)
        return result


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = DrawingNode()
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if executor:
            executor.shutdown(timeout_sec=5)
        if node:
            node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
