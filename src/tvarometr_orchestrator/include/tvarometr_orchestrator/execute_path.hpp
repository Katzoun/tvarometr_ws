#ifndef TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_
#define TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/time.hpp"
#include "robot_control_msgs/action/execute_pose_array.hpp"

namespace tvarometr_orchestrator
{

/// Sends one cartesian path to the robot and waits until the robot has driven it.
///
/// The driver's goal ends when the arm stands still, not when the last point has
/// been queued, so SUCCESS here means the pen has actually stopped moving.
///
/// Halting it - an abort from the keyboard - cancels the goal, and the driver
/// treats that as an orderly stop: whatever is already in the RAPID queue still
/// runs out. That is not an emergency stop and is not meant to be one.
class ExecutePath : public BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>
{
public:
  ExecutePath(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  BT::NodeStatus onFeedback(const std::shared_ptr<const Feedback> feedback) override;

  // The overload that also carries the result, because an aborted goal says why
  // in its message. Pulled in by name so the other overload is not hidden.
  using BT::RosActionNode<robot_control_msgs::action::ExecutePoseArray>::onFailure;
  BT::NodeStatus onFailure(
    BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result) override;

private:
  // The driver reports every point it sends and every poll while it waits.
  // Logging all of that would bury everything else, so progress is written at
  // most every couple of seconds.
  rclcpp::Time last_progress_log_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__EXECUTE_PATH_HPP_
