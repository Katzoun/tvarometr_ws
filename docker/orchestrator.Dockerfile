# Orchestrator container: the behaviour tree. CPU only.
# Dependencies only - source is mounted by Compose and built with colcon inside.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble \
    COLCON_DEFAULTS_FILE=/colcon-defaults.yaml \
    BASH_ENV=/ros-env.sh

# clangd for the editor, gdb for the debugger.
RUN apt-get update && apt-get install -y --no-install-recommends \
        clangd \
        gdb \
        python3-colcon-common-extensions \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Manifests only: the source itself is mounted at run time. robot_control_msgs
# belongs to the driver's repository and behaviortree_ros2 is third party, so
# `vcs import src < dependencies.repos` has to have run before this image is
# built - otherwise the COPY below fails.
COPY src/tvarometr_orchestrator/package.xml /tmp/deps/tvarometr_orchestrator/package.xml
COPY src/tvarometr_interfaces/package.xml /tmp/deps/tvarometr_interfaces/package.xml
COPY src/tvarometr_geometry/package.xml /tmp/deps/tvarometr_geometry/package.xml
COPY src/abb_rws2_ros2_driver/robot_control_msgs/package.xml /tmp/deps/robot_control_msgs/package.xml
COPY src/behaviortree_ros2/behaviortree_ros2/package.xml /tmp/deps/behaviortree_ros2/package.xml
COPY src/behaviortree_ros2/btcpp_ros2_interfaces/package.xml /tmp/deps/btcpp_ros2_interfaces/package.xml
RUN apt-get update \
    && rosdep update --rosdistro ${ROS_DISTRO} \
    && rosdep install --from-paths /tmp/deps --ignore-src --rosdistro ${ROS_DISTRO} -y \
    && rm -rf /tmp/deps /var/lib/apt/lists/*

# behaviortree_cpp 4.9.1 for Humble installs its library into the multiarch
# subdirectory while its own CMake export looks for it one level up, so
# find_package(behaviortree_cpp) fails on a package it just installed. One
# symlink is the whole fix. The -mindepth keeps this a no-op once the Debian
# package puts the library where its export expects it.
RUN set -eux; \
    lib="$(find /opt/ros/${ROS_DISTRO}/lib -mindepth 2 -name 'libbehaviortree_cpp.so' -print -quit)"; \
    if [ -n "$lib" ]; then ln -s "$lib" /opt/ros/${ROS_DISTRO}/lib/libbehaviortree_cpp.so; fi

# The drawing node's font, which rosdep has no rule for.
COPY docker/requirements-orchestrator.txt /tmp/requirements-orchestrator.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-orchestrator.txt

WORKDIR /workspace
COPY docker/colcon-defaults-orchestrator.yaml /colcon-defaults.yaml
COPY docker/ros-env.sh /ros-env.sh
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /ros-env.sh \
    && echo 'source /ros-env.sh' >> /root/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
