cmake_minimum_required(VERSION 3.8)
project(tvarometr_orchestrator)

# gcc defaults to C++17, clang to C++14, so clangd would flag code that builds.
# Extensions off forces -std into compile_commands; CMake omits it otherwise.
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(behaviortree_ros2 REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(lifecycle_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(robot_control_msgs REQUIRED)
find_package(tvarometr_interfaces REQUIRED)

add_executable(orchestrator_node
  src/generate_trajectories.cpp
  src/lifecycle_nodes.cpp
  src/log_message.cpp
  src/mock_action.cpp
  src/mock_inference.cpp
  src/operator_input.cpp
  src/orchestrator_node.cpp
  src/run_inference.cpp
)
target_include_directories(orchestrator_node PRIVATE include)
ament_target_dependencies(orchestrator_node
  ament_index_cpp
  behaviortree_cpp
  behaviortree_ros2
  geometry_msgs
  lifecycle_msgs
  rclcpp
  rclcpp_action
  robot_control_msgs
  tvarometr_interfaces
)

install(TARGETS orchestrator_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY behavior_trees launch
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  # No file in this repository carries a licence header. cpplint checks for one
  # too, and is told not to by CPPLINT.cfg next to this file - everything else
  # it catches still runs.
  set(ament_cmake_copyright_FOUND TRUE)

  # Python here is linted by ruff, which does not turn pydocstyle on. Letting
  # pep257 loose on the launch file would demand a docstring style that no
  # other Python file in the repository follows.
  set(ament_cmake_pep257_FOUND TRUE)

  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
