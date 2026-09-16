"""The centring node with its settings, which are the cell's own numbers.

A launch file and not a plain run because min_z and max_z have to come from
config/centring.yaml - defaults that fit no cell are worth nothing here.
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

    centring_node = Node(
        package="tvarometr_geometry",
        executable="centring_node_exec",
        name="centring_node",
        output="screen",
        parameters=[LaunchConfiguration("config")],
        emulate_tty=True,
    )

    return LaunchDescription([config_arg, centring_node])
