"""Both geometry nodes at once: trajectories and centring.

One command for the pair, which is what the orchestrator container runs. The
tree is not here: it reads the keyboard, so it is started attached instead.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share_dir = get_package_share_directory("tvarometr_geometry")

    config_arg = DeclareLaunchArgument(
        "config",
        default_value=os.path.join(share_dir, "config", "centring.yaml"),
        description="YAML with the centring parameters (Z limits, gain, target)",
    )

    trajectory_node = Node(
        package="tvarometr_geometry",
        executable="trajectory_node_exec",
        name="trajectory_node",
        output="screen",
        emulate_tty=True,
    )

    centring_node = Node(
        package="tvarometr_geometry",
        executable="centring_node_exec",
        name="centring_node",
        output="screen",
        parameters=[LaunchConfiguration("config")],
        emulate_tty=True,
    )

    return LaunchDescription([config_arg, trajectory_node, centring_node])
