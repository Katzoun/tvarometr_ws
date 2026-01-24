#!/bin/bash

# Nastavení workspace
WORKSPACE_DIR="$HOME/tvarometr_ws_SOTA"
cd "$WORKSPACE_DIR"

# Sourcing ROS2
source /opt/ros/humble/setup.bash
source install/setup.bash

# Spuštění nodů v oddělených terminálech pomocí gnome-terminal
gnome-terminal --window-with-profile=Default --title="Master Node" -- bash -c "cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo '=== MASTER NODE ===' && ros2 run master_pkg master_node_exec; exec bash" &

gnome-terminal --window-with-profile=Default --title="Inference Node" -- bash -c "cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo '=== INFERENCE NODE ===' && ros2 run camera inference_node_exec; exec bash" &

gnome-terminal --window-with-profile=Default --title="Camera Node" -- bash -c "cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo '=== CAMERA NODE ===' && ros2 run camera camera_node_exec; exec bash" &

gnome-terminal --window-with-profile=Default --title="Keyboard Node" -- bash -c "cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo '=== KEYBOARD NODE ===' && ros2 run master_pkg keyboard_publisher_exec; exec bash" &

gnome-terminal --window-with-profile=Default --title="Turtle Simulator" -- bash -c "cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo '=== TURTLE SIMULATOR ===' && ros2 run master_pkg turtle_drawer_exec; exec bash" &

echo "Všechny nody spuštěny v oddělených oknech gnome-terminal"
