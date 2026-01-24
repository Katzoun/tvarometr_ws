#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch.substitutions import PythonExpression


def generate_launch_description():
    # Launch arguments
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
    
    # Get launch configuration
    use_rws = LaunchConfiguration('use_rws')
    generate_csv = LaunchConfiguration('generate_csv')
    
    # Master node - the main control node
    master_node = Node(
        package='master_pkg',
        executable='master_node_exec',
        name='master_node',
        output='screen',
        parameters=[{
            'use_rws': use_rws,
            'generate_csv': generate_csv
        }],
        emulate_tty=True
    )

    # Face inference node - AI face attribute detection
    inference_node = Node(
        package='camera',
        executable='inference_node_exec',
        name='inference_node',
        output='screen',
        emulate_tty=True
    )
    
    # Camera node - webcam capture and image publishing
    camera_node = Node(
        package='camera',
        executable='camera_node_exec',
        name='camera_node',
        output='screen',
        emulate_tty=True
    )
    
    # Keyboard node - keyboard input handling
    keyboard_node = Node(
        package='master_pkg',
        executable='keyboard_publisher_exec',
        name='keyboard_node',
        output='screen',
        emulate_tty=True
    )
    
    # Turtle simulator node (only when not using RWS)
    turtle_node = Node(
        package='master_pkg',
        executable='turtle_drawer_exec',
        name='turtle_node',
        output='screen',
        emulate_tty=True,
        condition=IfCondition(PythonExpression(['"', use_rws, '" == "false"']))
    )
    
    return LaunchDescription([
        # Launch arguments
        use_rws_arg,
        generate_csv_arg,
        
        # Log startup message
        LogInfo(msg="Starting Tvarometr Face Detection and Drawing System..."),
        
        # Launch all nodes
        master_node,
        inference_node,
        camera_node,
        keyboard_node,
        turtle_node,  # Only launches when use_rws=false
        
        LogInfo(msg="All nodes launched. System ready!")
    ])
