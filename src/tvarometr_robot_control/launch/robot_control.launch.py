#!/usr/bin/env python3
"""Robot controller node - the RWS side of the system.

A managed node: it comes up unconfigured and does nothing until driven through
the lifecycle. Configure logs in to the controller, activate starts the keepalive
and joint state timers and opens it up for motion goals:

    ros2 lifecycle set /robot_controller configure
    ros2 lifecycle set /robot_controller activate
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    args = [
        DeclareLaunchArgument('robot_ip', default_value='192.168.0.37'),
        DeclareLaunchArgument('robot_port', default_value='443'),
        DeclareLaunchArgument('robot_username', default_value='Admin'),
        DeclareLaunchArgument('robot_password', default_value='robotics'),
        DeclareLaunchArgument(
            'send_joint_states', default_value='true',
            description='Publish the robot pose as sensor_msgs/JointState'),
    ]

    robot_controller_node = Node(
        package='tvarometr_robot_control',
        executable='robot_controller_node_exec',
        name='robot_controller',
        output='screen',
        parameters=[{
            'connection.ip_address': LaunchConfiguration('robot_ip'),
            'connection.port': LaunchConfiguration('robot_port'),
            'connection.username': LaunchConfiguration('robot_username'),
            'connection.password': LaunchConfiguration('robot_password'),
            'utility.send_joint_states': LaunchConfiguration('send_joint_states'),
        }],
        emulate_tty=True
    )

    return LaunchDescription(args + [
        LogInfo(msg="Starting Tvarometr robot controller..."),
        robot_controller_node,
    ])
