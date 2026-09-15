#!/usr/bin/env python3
"""Camera driver + inference - the GPU container half of the system.

The camera comes from camera.launch.py; the inference node is managed, so it
comes up unconfigured until configure loads the weights. Its settings live in
config/inference.yaml."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode


def generate_launch_description():
    share_dir = get_package_share_directory('tvarometr_inference')

    config_arg = DeclareLaunchArgument(
        'config',
        default_value=os.path.join(share_dir, 'config', 'inference.yaml'),
        description='YAML with the inference node parameters (device, models_dir, image_topic)'
    )
    use_camera_arg = DeclareLaunchArgument(
        'use_camera',
        default_value='true',
        description='Start the camera. Turn it off on a machine with no webcam - '
                    'the inference node still picks up whatever publishes /image_raw'
    )

    camera = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share_dir, 'launch', 'camera.launch.py')),
        condition=IfCondition(LaunchConfiguration('use_camera')),
    )

    inference_node = LifecycleNode(
        package='tvarometr_inference',
        executable='inference_node_exec',
        name='inference_node',
        namespace='',
        output='screen',
        parameters=[LaunchConfiguration('config')],
        emulate_tty=True
    )

    return LaunchDescription([
        config_arg,
        use_camera_arg,
        LogInfo(msg="Starting Tvarometr inference stack (camera + models)..."),
        camera,
        inference_node,
    ])
