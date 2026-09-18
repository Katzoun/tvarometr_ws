# Orchestrator container: the behaviour tree. CPU only.
# Dependencies only - source is mounted by Compose and built with colcon inside.

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    ROS_DISTRO=humble \
    COLCON_DEFAULTS_FILE=/colcon-defaults.yaml \
    BASH_ENV=/ros-env.sh

# Czech mirror: Canonical's archive crawls from here and security.ubuntu.com
# does not answer. Swap it outside Europe.
RUN sed -i \
    -e 's|http://archive.ubuntu.com|http://cz.archive.ubuntu.com|g' \
    -e 's|http://security.ubuntu.com|http://cz.archive.ubuntu.com|g' \
    /etc/apt/sources.list

# clangd for the editor, gdb for the debugger, git-lfs for the weights in models/.
RUN apt-get update && apt-get install -y --no-install-recommends \
        clangd \
        gdb \
        git-lfs \
        python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Manifests only, for rosdep; needs `vcs import src < dependencies.repos` first.
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

# behaviortree_cpp 4.9.1 installs its library a directory below where its CMake
# export looks. The symlink fixes find_package and is a no-op once upstream is fixed.
RUN set -eux; \
    lib="$(find /opt/ros/${ROS_DISTRO}/lib -mindepth 2 -name 'libbehaviortree_cpp.so' -print -quit)"; \
    if [ -n "$lib" ]; then ln -s "$lib" /opt/ros/${ROS_DISTRO}/lib/libbehaviortree_cpp.so; fi

# svg.path has no rosdep rule. Installed after rosdep, so each list keeps its layer cached.
COPY docker/requirements-orchestrator.txt /tmp/requirements-orchestrator.txt
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir -r /tmp/requirements-orchestrator.txt

WORKDIR /workspace
COPY docker/colcon-defaults-orchestrator.yaml /colcon-defaults.yaml
COPY docker/ros-env.sh /ros-env.sh
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /ros-env.sh \
    && echo 'source /ros-env.sh' >> /root/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
