#ifndef TVAROMETR_ORCHESTRATOR__MOVE_TO_JOINTS_HPP_
#define TVAROMETR_ORCHESTRATOR__MOVE_TO_JOINTS_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "robot_control_msgs/action/execute_joint_array.hpp"

namespace tvarometr_orchestrator
{

/// Moves the arm to fixed axis angles, in degrees, and waits until it is there.
///
/// Joints name one arm configuration; a robtarget could be reached wrist-flipped.
class MoveToJoints : public BT::RosActionNode<robot_control_msgs::action::ExecuteJointArray>
{
public:
  MoveToJoints(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<robot_control_msgs::action::ExecuteJointArray>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  using BT::RosActionNode<robot_control_msgs::action::ExecuteJointArray>::onFailure;
  BT::NodeStatus onFailure(
    BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__MOVE_TO_JOINTS_HPP_
