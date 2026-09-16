"""The centring node with config/centring.yaml, where the cell's Z limits live."""

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
