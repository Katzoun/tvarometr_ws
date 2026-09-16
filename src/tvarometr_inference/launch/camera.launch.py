"""The webcam alone: set its V4L2 controls, then stream /image_raw/compressed.

Run it by itself to tune the camera; inference.launch.py includes it.
"""

import os
import subprocess

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def apply_controls(context):
    camera_config = LaunchConfiguration("camera_config").perform(context)
    controls_file = LaunchConfiguration("camera_controls").perform(context)

    with open(camera_config) as f:
        device = yaml.safe_load(f)["/**"]["ros__parameters"]["video_device"]
    with open(controls_file) as f:
        controls = yaml.safe_load(f) or {}

    # One call per control, so a bad name costs only that control.
    actions = []
    for name, value in controls.items():
        result = subprocess.run(
            ["v4l2-ctl", "-d", device, f"--set-ctrl={name}={value}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            actions.append(LogInfo(msg=f"{device}: {name}={value}"))
        else:
            actions.append(
                LogInfo(
                    msg=f"{device}: could not set {name}={value}: {result.stderr.strip()}"
                )
            )

    actions.append(
        Node(
            package="tvarometr_inference",
            executable="camera_node_exec",
            name="camera",
            output="screen",
            parameters=[camera_config],
            emulate_tty=True,
        )
    )
    return actions


def generate_launch_description():
    config_dir = os.path.join(
        get_package_share_directory("tvarometr_inference"), "config"
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "camera_config",
                default_value=os.path.join(config_dir, "camera.yaml"),
                description="Camera parameters: device, resolution, framerate",
            ),
            DeclareLaunchArgument(
                "camera_controls",
                default_value=os.path.join(config_dir, "camera_controls.yaml"),
                description="V4L2 controls set before the camera starts: exposure, focus",
            ),
            OpaqueFunction(function=apply_controls),
        ]
    )
