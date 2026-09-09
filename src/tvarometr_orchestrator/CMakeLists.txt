cmake_minimum_required(VERSION 3.8)
project(tvarometr_orchestrator)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(robot_control_msgs REQUIRED)
find_package(tvarometr_interfaces REQUIRED)

add_executable(orchestrator_node src/orchestrator_node.cpp)
ament_target_dependencies(orchestrator_node
  ament_index_cpp
  behaviortree_cpp
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
