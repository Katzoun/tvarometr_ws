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
#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tvarometr_interfaces/action/run_inference.hpp"

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

/// Asks the vision node to run the models over its newest camera frame.
///
/// The action carries no goal fields - the node always works on whatever it
/// last received - so everything here is about the answer, which lands on the
/// blackboard for the drawing node to pick up.
class RunInference : public BT::RosActionNode<tvarometr_interfaces::action::RunInference>
{
public:
  RunInference(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<tvarometr_interfaces::action::RunInference>(name, config, params)
  {
  }

  static BT::PortsList providedPorts()
  {
    return providedBasicPorts(
      {BT::OutputPort<tvarometr_interfaces::msg::FaceAttributes>(
          "attributes", "Age, gender, emotion, and where the face sat in the frame")});
  }

  bool setGoal(Goal & /*goal*/) override
  {
    return true;
  }

  BT::NodeStatus onResultReceived(const WrappedResult & result) override
  {
    if (!result.result->success) {
      RCLCPP_ERROR(logger(), "Inference failed: %s", result.result->message.c_str());
      return BT::NodeStatus::FAILURE;
    }
    setOutput("attributes", result.result->attributes);
    RCLCPP_INFO(logger(), "Inference: %s", result.result->message.c_str());
    return BT::NodeStatus::SUCCESS;
  }

  BT::NodeStatus onFailure(BT::ActionNodeErrorCode error) override
  {
    RCLCPP_ERROR(logger(), "Inference action failed: %s", BT::toStr(error));
    return BT::NodeStatus::FAILURE;
  }
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

  // The action server lives in the vision container. Its default name is set
  // here rather than in the tree, so the XML stays about behaviour.
  BT::RosNodeParams inference_params(node, "/inference_node/run_inference");
  factory.registerNodeType<tvarometr_orchestrator::RunInference>("RunInference", inference_params);

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
