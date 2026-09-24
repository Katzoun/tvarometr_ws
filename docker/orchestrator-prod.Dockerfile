# Orchestrator for a run: the dev image's dependencies with the source built in
# instead of mounted. The tree itself is not the command - it reads the
# keyboard, so it is started attached with `docker exec -it`.

FROM tvarometr/orchestrator:dev

# The paths colcon-defaults-orchestrator.yaml already points at.
COPY src/tvarometr_interfaces /workspace/src/tvarometr_interfaces
COPY src/tvarometr_geometry /workspace/src/tvarometr_geometry
COPY src/tvarometr_orchestrator /workspace/src/tvarometr_orchestrator
COPY src/behaviortree_ros2 /workspace/src/behaviortree_ros2
COPY src/abb_rws2_ros2_driver/robot_control_msgs /workspace/src/robot_control_msgs

# Two jobs at a time: the C++ build runs an 8 GB machine out of RAM otherwise.
RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
    && MAKEFLAGS=-j2 colcon build --parallel-workers 1

CMD ["ros2", "launch", "tvarometr_geometry", "geometry.launch.py"]
