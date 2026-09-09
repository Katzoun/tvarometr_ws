#!/usr/bin/env python3
"""Starts the behaviour tree.

The tree runs once and the process exits with it, so this is not something you
leave running - you launch it when there is a face to draw.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_tree = os.path.join(
        get_package_share_directory('tvarometr_orchestrator'),
        'behavior_trees', 'tvarometr.xml')

    tree_file_arg = DeclareLaunchArgument(
        'tree_file',
        default_value=default_tree,
        description='Behaviour tree XML to run'
    )

    orchestrator_node = Node(
        package='tvarometr_orchestrator',
        executable='orchestrator_node',
        name='orchestrator',
        output='screen',
        parameters=[{'tree_file': LaunchConfiguration('tree_file')}],
        emulate_tty=True
    )

    return LaunchDescription([
        tree_file_arg,
        LogInfo(msg='Starting the Tvarometr orchestrator...'),
        orchestrator_node,
    ])
