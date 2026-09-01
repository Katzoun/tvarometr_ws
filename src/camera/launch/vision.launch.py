#!/usr/bin/env python3
"""Camera driver + inference - the GPU container half of the system.

usb_cam streams continuously on /image_raw; the inference node keeps the newest
frame and runs the models when master_pkg publishes on /start_inference."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    default_camera_config = os.path.join(
        get_package_share_directory('camera'), 'config', 'usb_cam.yaml')

    device_arg = DeclareLaunchArgument(
        'device',
        default_value='cpu',
        description='Inference device for the age/gender/emotion models (cpu or cuda:0)'
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

    inference_node = Node(
        package='camera',
        executable='inference_node_exec',
        name='inference_node',
        output='screen',
        parameters=[{'device': LaunchConfiguration('device')}],
        emulate_tty=True
    )

    return LaunchDescription([
        device_arg,
        camera_config_arg,
        use_camera_arg,
        LogInfo(msg="Starting Tvarometr vision stack (usb_cam + inference)..."),
        camera_node,
        inference_node,
    ])
