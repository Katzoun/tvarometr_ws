#!/usr/bin/env python3
"""Turns a face analysis into the paths the robot puts on the whiteboard.

Splitting this out of the master node means the geometry can be produced and
looked at without a robot, a camera or the state machine - hand it a
FaceAttributes message and you get the paths back.

The Czech values are decided here: FaceAttributes carries the models' own
English labels, and this is where they become words. The fixed column of
labels beside them belongs to the generator, which has to know their width to
work out where the value column starts.

Not a managed node, unlike the inference node and the driver. There is nothing
to acquire or release here - no weights, no session, no device - so a lifecycle
would be five callbacks guarding a boolean that guards itself.
"""

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Pose, PoseArray

from tvarometr_interfaces.srv import GenerateTrajectories

from tvarometr_geometry.path_generator import generate_trajectories

EMOTION_CS = {
    "anger": "naštvaný",
    "disgust": "znechucený",
    "fear": "vyděšený",
    "happiness": "šťastný",
    "sadness": "smutný",
    "surprise": "překvapený",
    "neutral": "neutrální",
}

GENDER_CS = {"male": "muž", "female": "žena"}


class TrajectoryNode(Node):

    def __init__(self):
        super().__init__('trajectory_node')
        self.NODE_NAME = 'trajectory_node'
        self.logger = self.get_logger()

        # Millimetres, like the generator's inputs. Its output is metres.
        self.declare_parameter('letter_height', 60.0)
        self.declare_parameter('letter_spacing', 10.0)
        self.declare_parameter('space_factor', 1.3)
        self.declare_parameter('line_spacing', 1.5)
        # How wide the value column is, and how much of the board the eraser
        # covers in one pass. Both decide where the sweep runs, so a value that
        # is wrong here is a value the robot wipes text over.
        self.declare_parameter('values_width', 600.0)
        self.declare_parameter('eraser_width', 20.0)
        self.declare_parameter('label_gap', 10.0)

        # The pen orientation every point is written with. Default is the
        # quaternion the master node has always sent - ABB [0,1,0,0] in w,x,y,z,
        # which is x,y,z,w = 1,0,0,0 the ROS way round.
        self.declare_parameter('pen_orientation', [1.0, 0.0, 0.0, 0.0])

        self.service = self.create_service(
            GenerateTrajectories,
            f'{self.NODE_NAME}/generate_trajectories',
            self.generate_cb,
        )

        self.logger.info('Ready - accepting trajectory requests')

    # ============= SERVICE =============

    def compose_values(self, attributes) -> str:
        """The three lines the generator expects: age, gender, mood."""
        gender = GENDER_CS.get(attributes.gender, attributes.gender)
        emotion = EMOTION_CS.get(attributes.emotion, attributes.emotion)
        return f'{attributes.age}\n{gender}\n{emotion}'

    def to_pose_array(self, points) -> PoseArray:
        qx, qy, qz, qw = self.get_parameter('pen_orientation').value
        path = PoseArray()
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y, z in points:
            pose = Pose()
            pose.position.x, pose.position.y, pose.position.z = float(x), float(y), float(z)
            pose.orientation.x, pose.orientation.y = qx, qy
            pose.orientation.z, pose.orientation.w = qz, qw
            path.poses.append(pose)
        return path

    def generate_cb(self, request, response):
        values = self.compose_values(request.attributes)
        self.logger.info(f'Generating trajectories for: {values!r}')

        try:
            paths = generate_trajectories(
                values,
                letter_height=self.get_parameter('letter_height').value,
                letter_spacing=self.get_parameter('letter_spacing').value,
                space_factor=self.get_parameter('space_factor').value,
                line_spacing=self.get_parameter('line_spacing').value,
                values_width=self.get_parameter('values_width').value,
                eraser_width=self.get_parameter('eraser_width').value,
                label_gap=self.get_parameter('label_gap').value,
            )
        except ValueError as error:
            # Text too wide for the column, or a character the font has no
            # glyph for. Both are the caller's problem to fix, not a crash.
            response.success = False
            response.message = str(error)
            self.logger.error(response.message)
            return response

        response.labels = self.to_pose_array(paths['labels'])
        response.values = self.to_pose_array(paths['values'])
        response.erase = self.to_pose_array(paths['erase'])

        # Nothing is appended to park the robot afterwards - moving away from the
        # board is the RAPID routine's business, not part of the text.
        response.success = True
        response.message = (
            f'{len(response.labels.poses)} label, {len(response.values.poses)} value '
            f'and {len(response.erase.poses)} erase points')
        self.logger.info(response.message)
        return response


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TrajectoryNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
