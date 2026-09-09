// The behaviour tree that will drive the whole run: ask the camera for a face,
// turn the analysis into a path, hand the path to the robot.
//
// Right now it only loads a tree and ticks it. The tree itself is nearly empty
// - what this proves is the wiring: that a C++ package here builds against the
// driver's robot_control_msgs, which comes from a different repository.

#include <memory>
#include <string>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "behaviortree_cpp/bt_factory.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// Writes a line to the ROS log.
///
/// A tree needs at least one node of its own to be worth loading, and this is
/// the smallest one that is still useful - it stays handy for marking progress
/// once the real nodes are in.
class LogMessage : public BT::SyncActionNode
{
public:
  LogMessage(const std::string & name, const BT::NodeConfig & config, rclcpp::Logger logger)
  : BT::SyncActionNode(name, config), logger_(logger)
  {
  }

  static BT::PortsList providedPorts()
  {
    return {BT::InputPort<std::string>("message", "What to write to the log")};
  }

  BT::NodeStatus tick() override
  {
    const auto message = getInput<std::string>("message");
    if (!message) {
      RCLCPP_ERROR(
        logger_, "LogMessage is missing its message port: %s",
        message.error().c_str());
      return BT::NodeStatus::FAILURE;
    }
    RCLCPP_INFO(logger_, "%s", message.value().c_str());
    return BT::NodeStatus::SUCCESS;
  }

private:
  rclcpp::Logger logger_;
};

}  // namespace tvarometr_orchestrator

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("orchestrator");

  const std::string installed_tree =
    ament_index_cpp::get_package_share_directory("tvarometr_orchestrator") +
    "/behavior_trees/tvarometr.xml";

  node->declare_parameter("tree_file", installed_tree);
  node->declare_parameter("tick_period_s", 0.1);

  const auto tree_file = node->get_parameter("tree_file").as_string();
  const auto tick_period = node->get_parameter("tick_period_s").as_double();

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<tvarometr_orchestrator::LogMessage>("LogMessage", node->get_logger());

  BT::Tree tree;
  try {
    tree = factory.createTreeFromFile(tree_file);
  } catch (const std::exception & e) {
    RCLCPP_FATAL(node->get_logger(), "Could not load %s: %s", tree_file.c_str(), e.what());
    rclcpp::shutdown();
    return 1;
  }
  RCLCPP_INFO(node->get_logger(), "Loaded %s", tree_file.c_str());

  // One pass over the tree, then out. A run has a beginning and an end; keeping
  // the process alive afterwards would only invite it to be treated as a daemon.
  rclcpp::Rate rate(1.0 / tick_period);
  BT::NodeStatus status = BT::NodeStatus::RUNNING;
  while (rclcpp::ok() && status == BT::NodeStatus::RUNNING) {
    status = tree.tickOnce();
    rclcpp::spin_some(node);
    rate.sleep();
  }

  RCLCPP_INFO(node->get_logger(), "Tree finished: %s", BT::toStr(status).c_str());
  rclcpp::shutdown();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
