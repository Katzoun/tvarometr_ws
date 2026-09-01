#!/usr/bin/env python3
"""Launches only the camera + inference nodes (the GPU-container half of the
system). Split out from tvarometr_system.launch.py so the vision workload can
run in its own Docker container, separate from the robot-control workload."""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    device_arg = DeclareLaunchArgument(
        'device',
        default_value='cpu',
        description='Inference device for the age/gender/emotion models (cpu or cuda:0)'
    )
    device = LaunchConfiguration('device')

    inference_node = Node(
        package='camera',
        executable='inference_node_exec',
        name='inference_node',
        output='screen',
        parameters=[{'device': device}],
        emulate_tty=True
    )

    camera_node = Node(
        package='camera',
        executable='camera_node_exec',
        name='camera_node',
        output='screen',
        emulate_tty=True
    )

    return LaunchDescription([
        device_arg,
        LogInfo(msg="Starting Tvarometr vision stack (camera + inference)..."),
        inference_node,
        camera_node,
    ])
