#!/bin/bash

# Nastavení workspace
WORKSPACE_DIR="$HOME/tvarometr_ws_SOTA"
cd "$WORKSPACE_DIR"

# Sourcing ROS2
source /opt/ros/humble/setup.bash
source install/setup.bash

# Získání rozlišení obrazovky
SCREEN_WIDTH=$(xrandr | grep '*' | awk '{print $1}' | cut -d'x' -f1 | head -1)
SCREEN_HEIGHT=$(xrandr | grep '*' | awk '{print $1}' | cut -d'x' -f2 | head -1)

# Layout: 3 okna nahoře, 2 okna dole
TOP_WIDTH=$((SCREEN_WIDTH / 3))
TOP_HEIGHT=$((SCREEN_HEIGHT / 2))
BOTTOM_WIDTH=$((SCREEN_WIDTH / 2))
BOTTOM_HEIGHT=$((SCREEN_HEIGHT / 2))

# Horní řada - 3 okna
# Master Node - levé horní
terminator -T "Master Node" --geometry=${TOP_WIDTH}x${TOP_HEIGHT}+0+0 -e "bash -c 'cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo \"=== MASTER NODE ===\" && ros2 run master_pkg master_node_exec; exec bash'" &

sleep 1

# Inference Node - střední horní
terminator -T "Inference Node" --geometry=${TOP_WIDTH}x${TOP_HEIGHT}+${TOP_WIDTH}+0 -e "bash -c 'cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo \"=== INFERENCE NODE ===\" && ros2 run camera inference_node_exec; exec bash'" &

sleep 1

# Camera Node - pravé horní
terminator -T "Camera Node" --geometry=${TOP_WIDTH}x${TOP_HEIGHT}+$((TOP_WIDTH * 2))+0 -e "bash -c 'cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo \"=== CAMERA NODE ===\" && ros2 run camera camera_node_exec; exec bash'" &

sleep 1

# Dolní řada - 2 okna
# Keyboard Node - levé dolní
terminator -T "Keyboard Node" --geometry=${BOTTOM_WIDTH}x${BOTTOM_HEIGHT}+0+${TOP_HEIGHT} -e "bash -c 'cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo \"=== KEYBOARD NODE ===\" && ros2 run master_pkg keyboard_publisher_exec; exec bash'" &

sleep 1

# Turtle Simulator - pravé dolní
terminator -T "Turtle Simulator" --geometry=${BOTTOM_WIDTH}x${BOTTOM_HEIGHT}+${BOTTOM_WIDTH}+${TOP_HEIGHT} -e "bash -c 'cd $WORKSPACE_DIR && source /opt/ros/humble/setup.bash && source install/setup.bash && echo \"=== TURTLE SIMULATOR ===\" && ros2 run master_pkg turtle_drawer_exec; exec bash'" &

echo "Všechny nody spuštěny v organizovaném layoutu"
echo "Layout:"
echo "  [Master]    [Inference]    [Camera]"
echo "  [Keyboard]     [Turtle]"
