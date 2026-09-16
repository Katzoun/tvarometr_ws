// Loads the behaviour tree and ticks it until Ctrl+C.
// The tree waits for the operator, runs a cycle and comes back to waiting.

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <memory>
#include <string>
#include <thread>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "behaviortree_cpp/bt_factory.h"
#include "behaviortree_cpp/loggers/abstract_logger.h"
#include "behaviortree_cpp/loggers/groot2_publisher.h"
#include "behaviortree_ros2/ros_node_params.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tvarometr_orchestrator/centre_face.hpp"
#include "tvarometr_orchestrator/execute_path.hpp"
#include "tvarometr_orchestrator/generate_trajectories.hpp"
#include "tvarometr_orchestrator/lifecycle_nodes.hpp"
#include "tvarometr_orchestrator/log_message.hpp"
#include "tvarometr_orchestrator/mock_action.hpp"
#include "tvarometr_orchestrator/mock_inference.hpp"
#include "tvarometr_orchestrator/move_to_joints.hpp"
#include "tvarometr_orchestrator/operator_input.hpp"
#include "tvarometr_orchestrator/robot_request.hpp"
#include "tvarometr_orchestrator/run_inference.hpp"

namespace
{

/// StdCoutLogger without IsAbortClear, which the guard re-checks on every tick.
class QuietCoutLogger : public BT::StatusChangeLogger
{
public:
  explicit QuietCoutLogger(const BT::Tree & tree)
  : BT::StatusChangeLogger(tree.rootNode())
  {
  }

  void flush() override {std::fflush(stdout);}

private:
  void callback(
    BT::Duration timestamp, const BT::TreeNode & node, BT::NodeStatus prev_status,
    BT::NodeStatus status) override
  {
    if (node.registrationName() == "IsAbortClear") {
      return;
    }
    const std::string padding(25 - std::min<std::size_t>(24, node.name().size()), ' ');
    std::printf(
      "[%.3f]: %s%s%s -> %s\n", std::chrono::duration<double>(timestamp).count(),
      node.name().c_str(), padding.c_str(), BT::toStr(prev_status, true).c_str(),
      BT::toStr(status, true).c_str());
    std::fflush(stdout);
  }
};

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("orchestrator");

  const std::string installed_tree =
    ament_index_cpp::get_package_share_directory("tvarometr_orchestrator") +
    "/behavior_trees/tvarometr.xml";

  node->declare_parameter("tree_file", installed_tree);
  // Fast, so E halts a step at once and ROS timeouts fire on time.
  node->declare_parameter("tick_period_s", 0.05);
  node->declare_parameter("groot2_port", 1667);

  const auto tree_file = node->get_parameter("tree_file").as_string();
  const auto tick_period = node->get_parameter("tick_period_s").as_double();
  const auto groot2_port = node->get_parameter("groot2_port").as_int();

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<tvarometr_orchestrator::LogMessage>("LogMessage", node->get_logger());

  // Server names live here, so the XML stays about behaviour.
  BT::RosNodeParams inference_params(node, "/inference_node/run_inference");
  factory.registerNodeType<tvarometr_orchestrator::RunInference>("RunInference", inference_params);

  // Only acceptance is timed; the scan itself reports through feedback.
  BT::RosNodeParams centring_params(node, "/centring_node/centre_face");
  centring_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::CentreFace>("CentreFace", centring_params);

  // A couple of milliseconds, well within the library's one-second default.
  BT::RosNodeParams trajectory_params(node, "/trajectory_node/generate_trajectories");
  factory.registerNodeType<tvarometr_orchestrator::GenerateTrajectories>(
    "GenerateTrajectories", trajectory_params);

  // Acceptance costs the driver an RWS round trip, and an abort waits this long
  // for the cancelled goal's result.
  BT::RosNodeParams motion_params(node, "/robot_controller/robot_robtarget_move");
  motion_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::ExecutePath>("ExecutePath", motion_params);

  // Same driver, same waits, so the same timeout.
  BT::RosNodeParams joint_params(node, "/robot_controller/robot_jointtarget_move");
  joint_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::MoveToJoints>("MoveToJoints", joint_params);

  // make_robot_ready may start the motors and RAPID, settling after each.
  BT::RosNodeParams request_params(node, "/robot_controller/controller_request");
  request_params.server_timeout = std::chrono::seconds(15);
  factory.registerNodeType<tvarometr_orchestrator::RobotRequest>("RobotRequest", request_params);

  // Configuring the inference node loads the weights before it answers.
  BT::RosNodeParams lifecycle_params(node);
  lifecycle_params.server_timeout = std::chrono::minutes(2);
  factory.registerNodeType<tvarometr_orchestrator::ChangeLifecycleState>(
    "ChangeLifecycleState", lifecycle_params);

  // get_state answers at once; longer would only delay noticing a dead node.
  BT::RosNodeParams state_params(node);
  state_params.server_timeout = std::chrono::seconds(2);
  factory.registerNodeType<tvarometr_orchestrator::IsNodeActive>("IsNodeActive", state_params);

  // Operator keys, and the stand-ins for steps that are not real yet.
  tvarometr_orchestrator::OperatorInput operator_input;
  factory.registerNodeType<tvarometr_orchestrator::IsAbortClear>("IsAbortClear", &operator_input);
  factory.registerNodeType<tvarometr_orchestrator::WaitForKey>(
    "WaitForStart", &operator_input.start);
  factory.registerNodeType<tvarometr_orchestrator::WaitForKey>(
    "WaitForContinue", &operator_input.proceed);
  factory.registerNodeType<tvarometr_orchestrator::MockAction>("MockAction", node->get_logger());
  factory.registerNodeType<tvarometr_orchestrator::MockInference>(
    "MockInference", node->get_logger());

  BT::Tree tree;
  try {
    tree = factory.createTreeFromFile(tree_file);
  } catch (const std::exception & e) {
    RCLCPP_FATAL(node->get_logger(), "Could not load %s: %s", tree_file.c_str(), e.what());
    rclcpp::shutdown();
    return 1;
  }
  RCLCPP_INFO(node->get_logger(), "Loaded %s", tree_file.c_str());

  // Prints every state change in the tree.
  QuietCoutLogger tree_logger(tree);

  // Groot2 reaches this over the host network. A pointer, so a busy port cannot
  // stop the run.
  std::unique_ptr<BT::Groot2Publisher> groot2_publisher;
  try {
    groot2_publisher = std::make_unique<BT::Groot2Publisher>(
      tree, static_cast<unsigned>(groot2_port));
    RCLCPP_INFO(node->get_logger(), "Groot2 can connect on port %ld", groot2_port);
  } catch (const std::exception & e) {
    RCLCPP_WARN(node->get_logger(), "No Groot2 this run: %s", e.what());
  }

  // Only once the tree has loaded, so a bad tree cannot leave the terminal raw.
  std::thread keyboard(tvarometr_orchestrator::readKeyboard, &operator_input, node->get_logger());

  // Stops only on Ctrl+C. tree.sleep, because a ROS node with news wakes it early.
  const auto tick_duration = std::chrono::duration_cast<std::chrono::system_clock::duration>(
    std::chrono::duration<double>(tick_period));
  BT::NodeStatus status = BT::NodeStatus::RUNNING;
  while (rclcpp::ok() && status == BT::NodeStatus::RUNNING) {
    status = tree.tickOnce();
    rclcpp::spin_some(node);
    tree.sleep(tick_duration);
  }

  RCLCPP_INFO(node->get_logger(), "Tree finished: %s", BT::toStr(status).c_str());
  // shutdown() first, so the keyboard reader sees rclcpp::ok() go false.
  rclcpp::shutdown();
  keyboard.join();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
