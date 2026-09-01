#!/usr/bin/env python3
"""Launches the robot-control side of the system: master node, keyboard input,
and (when not using the real robot) the turtlesim drawing preview. Split out
from tvarometr_system.launch.py so this can run in its own CPU-only Docker
container, separate from the GPU vision workload."""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch.substitutions import PythonExpression


def generate_launch_description():
    use_rws_arg = DeclareLaunchArgument(
        'use_rws',
        default_value='false',
        description='Use RWS connection to real robot (true) or turtle simulator (false)'
    )

    generate_csv_arg = DeclareLaunchArgument(
        'generate_csv',
        default_value='true',
        description='Generate CSV file with drawing points'
    )

    robot_ip_arg = DeclareLaunchArgument('robot_ip', default_value='192.168.0.37')
    robot_port_arg = DeclareLaunchArgument('robot_port', default_value='443')
    robot_username_arg = DeclareLaunchArgument('robot_username', default_value='Admin')
    robot_password_arg = DeclareLaunchArgument('robot_password', default_value='robotics')

    use_rws = LaunchConfiguration('use_rws')
    generate_csv = LaunchConfiguration('generate_csv')

    master_node = Node(
        package='master_pkg',
        executable='master_node_exec',
        name='master_node',
        output='screen',
        parameters=[{
            'use_rws': use_rws,
            'generate_csv': generate_csv,
            'robot_ip': LaunchConfiguration('robot_ip'),
            'robot_port': LaunchConfiguration('robot_port'),
            'robot_username': LaunchConfiguration('robot_username'),
            'robot_password': LaunchConfiguration('robot_password'),
        }],
        emulate_tty=True
    )

    # keyboard_publisher is left out on purpose: it reads raw keys via termios,
    # which needs a controlling terminal that ros2 launch doesn't hand its children.
    # Bundled here it just dies with "Inappropriate ioctl for device". Run it in a
    # terminal of its own:
    #   docker exec -it tvarometr_control ros2 run master_pkg keyboard_publisher_exec

    turtle_node = Node(
        package='master_pkg',
        executable='turtle_drawer_exec',
        name='turtle_node',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(PythonExpression(['"', use_rws, '" == "false"']))
    )

    return LaunchDescription([
        use_rws_arg,
        generate_csv_arg,
        robot_ip_arg,
        robot_port_arg,
        robot_username_arg,
        robot_password_arg,
        LogInfo(msg="Starting Tvarometr control stack (master node)..."),
        master_node,
        turtle_node,
    ])
