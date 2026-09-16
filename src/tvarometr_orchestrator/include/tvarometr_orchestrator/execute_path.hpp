#ifndef TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_
#define TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/time.hpp"
#include "robot_control_msgs/action/execute_pose_array.hpp"
#include "tvarometr_orchestrator/pose_array_from_string.hpp"

namespace tvarometr_orchestrator
{

/// Sends one cartesian path and waits until the arm has stopped.
///
/// A halt cancels the goal; the driver still runs out its queue, so it is no e-stop.
class ExecutePath : public BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>
{
public:
  ExecutePath(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  BT::NodeStatus tick() override;

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  BT::NodeStatus onFeedback(const std::shared_ptr<const Feedback> feedback) override;

  // The overload that also carries the result, because an aborted goal says why
  // in its message. Pulled in by name so the other overload is not hidden.
  using BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>::onFailure;
  BT::NodeStatus onFailure(
    BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result) override;

private:
  // Progress is logged at most every couple of seconds.
  rclcpp::Time last_progress_log_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_
