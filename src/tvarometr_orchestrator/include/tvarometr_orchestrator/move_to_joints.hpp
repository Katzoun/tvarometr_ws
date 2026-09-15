#ifndef TVAROMETR_ORCHESTRATOR__MOVE_TO_JOINTS_HPP_
#define TVAROMETR_ORCHESTRATOR__MOVE_TO_JOINTS_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "robot_control_msgs/action/execute_joint_array.hpp"

namespace tvarometr_orchestrator
{

/// Moves the arm to one fixed set of axis angles and waits until it is there.
///
/// For the poses the run keeps coming back to, like the one the camera
/// photographs from. Joint space rather than a cartesian target, because axis
/// angles name exactly one arm configuration - a robtarget for a fixed pose can
/// be reached with the wrist flipped, and which one the controller picks is
/// not something to find out with a visitor standing in front of it.
///
/// The angles are degrees, the unit the FlexPendant and RobotStudio show, so a
/// pose jogged to by hand can be copied straight into the tree file.
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
