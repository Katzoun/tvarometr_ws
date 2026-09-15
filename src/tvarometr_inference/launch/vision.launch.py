#!/usr/bin/env python3
"""Camera driver + inference - the GPU container half of the system.

usb_cam streams continuously on /image_raw; the inference node keeps the newest
frame and runs the models when it is sent a RunInference goal. It is a managed
node, so it comes up unconfigured - configure is what loads the weights.

The node's settings - device, where the weights are, which topic to read - live
in config/inference.yaml, the camera's in config/usb_cam.yaml."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import LifecycleNode, Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    config_dir = os.path.join(get_package_share_directory('tvarometr_inference'), 'config')
    default_config = os.path.join(config_dir, 'inference.yaml')
    default_camera_config = os.path.join(config_dir, 'usb_cam.yaml')

    config_arg = DeclareLaunchArgument(
        'config',
        default_value=default_config,
        description='YAML with the inference node parameters (device, models_dir, image_topic)'
    )
    camera_config_arg = DeclareLaunchArgument(
        'camera_config',
        default_value=default_camera_config,
        description='YAML with usb_cam parameters (resolution, framerate, device path)'
    )
    use_camera_arg = DeclareLaunchArgument(
        'use_camera',
        default_value='true',
        description='Start the camera driver. Turn it off on a machine with no webcam - '
                    'the inference node still runs and picks up whatever publishes /image_raw'
    )

    camera_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        output='screen',
        parameters=[LaunchConfiguration('camera_config')],
        condition=IfCondition(LaunchConfiguration('use_camera')),
        emulate_tty=True
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
        camera_config_arg,
        use_camera_arg,
        LogInfo(msg="Starting Tvarometr vision stack (usb_cam + inference)..."),
        camera_node,
        inference_node,
    ])
