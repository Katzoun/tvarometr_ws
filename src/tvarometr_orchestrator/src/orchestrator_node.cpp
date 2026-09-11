// Loads the behaviour tree and ticks it until it stops.
//
// The tree waits for the operator, runs a cycle and comes back to waiting, so
// this process is the whole run. Most steps are still MockAction while the
// shape of the tree is what is being designed; a step becomes real by renaming
// it in the tree file, not by changing anything here.

#include <chrono>
#include <memory>
#include <string>
#include <thread>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "behaviortree_cpp/bt_factory.h"
#include "behaviortree_cpp/loggers/bt_cout_logger.h"
#include "behaviortree_cpp/loggers/groot2_publisher.h"
#include "behaviortree_ros2/ros_node_params.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tvarometr_orchestrator/generate_trajectories.hpp"
#include "tvarometr_orchestrator/lifecycle_nodes.hpp"
#include "tvarometr_orchestrator/log_message.hpp"
#include "tvarometr_orchestrator/mock_action.hpp"
#include "tvarometr_orchestrator/mock_inference.hpp"
#include "tvarometr_orchestrator/operator_input.hpp"
#include "tvarometr_orchestrator/run_inference.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("orchestrator");

  const std::string installed_tree =
    ament_index_cpp::get_package_share_directory("tvarometr_orchestrator") +
    "/behavior_trees/tvarometr.xml";

  node->declare_parameter("tree_file", installed_tree);
  node->declare_parameter("tick_period_s", 0.1);
  node->declare_parameter("groot2_port", 1667);

  const auto tree_file = node->get_parameter("tree_file").as_string();
  const auto tick_period = node->get_parameter("tick_period_s").as_double();
  const auto groot2_port = node->get_parameter("groot2_port").as_int();

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<tvarometr_orchestrator::LogMessage>("LogMessage", node->get_logger());

  // The action server lives in the vision container. Its default name is set
  // here rather than in the tree, so the XML stays about behaviour.
  BT::RosNodeParams inference_params(node, "/inference_node/run_inference");
  factory.registerNodeType<tvarometr_orchestrator::RunInference>("RunInference", inference_params);

  // Plain geometry, a couple of milliseconds, so the library's one-second
  // default timeout is left alone.
  BT::RosNodeParams trajectory_params(node, "/trajectory_node/generate_trajectories");
  factory.registerNodeType<tvarometr_orchestrator::GenerateTrajectories>(
    "GenerateTrajectories", trajectory_params);

  // Configure on the inference node loads half a gigabyte of weights and the
  // service answers only once it is done, so the library's one-second default
  // would call every bring-up a timeout.
  BT::RosNodeParams lifecycle_params(node);
  lifecycle_params.server_timeout = std::chrono::minutes(2);
  factory.registerNodeType<tvarometr_orchestrator::ChangeLifecycleState>(
    "ChangeLifecycleState", lifecycle_params);

  // get_state answers at once. Waiting longer here would only delay noticing
  // that a node has gone away.
  BT::RosNodeParams state_params(node);
  state_params.server_timeout = std::chrono::seconds(2);
  factory.registerNodeType<tvarometr_orchestrator::IsNodeActive>("IsNodeActive", state_params);

  // Registered but unused until the tree file asks for them. The two above are
  // in the same position, which is the point of a skeleton: a step becomes real
  // by renaming it in the XML.
  tvarometr_orchestrator::OperatorInput operator_input;
  factory.registerNodeType<tvarometr_orchestrator::IsAbortClear>("IsAbortClear", &operator_input);
  factory.registerNodeType<tvarometr_orchestrator::WaitForStart>("WaitForStart", &operator_input);
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

  // Prints every state change a node goes through, which is what a tick
  // actually looks like.
  BT::StdCoutLogger tree_logger(tree);

  // Groot2 attaches over TCP and draws the tree as it ticks. The container is
  // on the host network, so a Groot2 running on the host reaches this port with
  // no mapping. Held by pointer because a busy port must not take the run down
  // with it - this is a window onto the run, not part of it.
  std::unique_ptr<BT::Groot2Publisher> groot2_publisher;
  try {
    groot2_publisher = std::make_unique<BT::Groot2Publisher>(
      tree, static_cast<unsigned>(groot2_port));
    RCLCPP_INFO(node->get_logger(), "Groot2 can connect on port %ld", groot2_port);
  } catch (const std::exception & e) {
    RCLCPP_WARN(node->get_logger(), "No Groot2 this run: %s", e.what());
  }

  // Started only once the tree has loaded, so a bad tree file cannot leave the
  // terminal stuck out of line mode.
  std::thread keyboard(tvarometr_orchestrator::readKeyboard, &operator_input, node->get_logger());

  // An abort sends the tree back to waiting rather than ending it, so in normal
  // use this loop only stops on Ctrl+C.
  rclcpp::Rate rate(1.0 / tick_period);
  BT::NodeStatus status = BT::NodeStatus::RUNNING;
  while (rclcpp::ok() && status == BT::NodeStatus::RUNNING) {
    status = tree.tickOnce();
    rclcpp::spin_some(node);
    rate.sleep();
  }

  RCLCPP_INFO(node->get_logger(), "Tree finished: %s", BT::toStr(status).c_str());
  // shutdown() first: it is what makes rclcpp::ok() false and lets the reader
  // fall out of its loop and hand the terminal back.
  rclcpp::shutdown();
  keyboard.join();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
