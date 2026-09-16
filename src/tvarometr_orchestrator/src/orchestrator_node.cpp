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

/// BT.CPP's StdCoutLogger, minus IsAbortClear. The guard re-checks it on every
/// tick, so at the tick rate below it would bury every other line twenty times
/// a second.
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
  // Fast, so that E halts a step at once and a ROS node's timeout fires when it
  // is due rather than up to a tick later. The tree also wakes early when such
  // a node has news - see the loop below.
  node->declare_parameter("tick_period_s", 0.05);
  node->declare_parameter("groot2_port", 1667);

  const auto tree_file = node->get_parameter("tree_file").as_string();
  const auto tick_period = node->get_parameter("tick_period_s").as_double();
  const auto groot2_port = node->get_parameter("groot2_port").as_int();

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<tvarometr_orchestrator::LogMessage>("LogMessage", node->get_logger());

  // The action server lives in the inference container. Its default name is set
  // here rather than in the tree, so the XML stays about behaviour.
  BT::RosNodeParams inference_params(node, "/inference_node/run_inference");
  factory.registerNodeType<tvarometr_orchestrator::RunInference>("RunInference", inference_params);

  // The centring node answers at once; the scan itself runs for as long as it
  // takes and reports through feedback, which no timeout here touches.
  BT::RosNodeParams centring_params(node, "/centring_node/centre_face");
  centring_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::CentreFace>("CentreFace", centring_params);

  // Plain geometry, a couple of milliseconds, so the library's one-second
  // default timeout is left alone.
  BT::RosNodeParams trajectory_params(node, "/trajectory_node/generate_trajectories");
  factory.registerNodeType<tvarometr_orchestrator::GenerateTrajectories>(
    "GenerateTrajectories", trajectory_params);

  // The timeout covers two waits. Accepting a goal costs the driver a round trip
  // to the controller to check RAPID is idle, which can outlast the one-second
  // default. And an abort blocks the tick while the cancel is acknowledged and
  // the result collected - the arm is still running out its queue then, so this
  // is also how long the tree stays frozen before it gives up on that result.
  BT::RosNodeParams motion_params(node, "/robot_controller/robot_robtarget_move");
  motion_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::ExecutePath>("ExecutePath", motion_params);

  // Same driver, same waits, so the same timeout.
  BT::RosNodeParams joint_params(node, "/robot_controller/robot_jointtarget_move");
  joint_params.server_timeout = std::chrono::seconds(3);
  factory.registerNodeType<tvarometr_orchestrator::MoveToJoints>("MoveToJoints", joint_params);

  // make_robot_ready is the slow one: when RAPID is not running it turns the
  // motors on, resets the program pointer and starts it, with a second's settle
  // after each. The library's one-second default would fail it every time it
  // has real work to do.
  BT::RosNodeParams request_params(node, "/robot_controller/controller_request");
  request_params.server_timeout = std::chrono::seconds(15);
  factory.registerNodeType<tvarometr_orchestrator::RobotRequest>("RobotRequest", request_params);

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

  // Prints every state change a node goes through, which is what a tick
  // actually looks like.
  QuietCoutLogger tree_logger(tree);

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
  //
  // tree.sleep and not a fixed-rate sleep: a ROS node that has just read a
  // result or feedback for its own goal wakes the tree to act on it at once.
  const auto tick_duration = std::chrono::duration_cast<std::chrono::system_clock::duration>(
    std::chrono::duration<double>(tick_period));
  BT::NodeStatus status = BT::NodeStatus::RUNNING;
  while (rclcpp::ok() && status == BT::NodeStatus::RUNNING) {
    status = tree.tickOnce();
    rclcpp::spin_some(node);
    tree.sleep(tick_duration);
  }

  RCLCPP_INFO(node->get_logger(), "Tree finished: %s", BT::toStr(status).c_str());
  // shutdown() first: it is what makes rclcpp::ok() false and lets the reader
  // fall out of its loop and hand the terminal back.
  rclcpp::shutdown();
  keyboard.join();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
