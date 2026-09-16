#ifndef TVAROMETR_ORCHESTRATOR__CENTRE_FACE_HPP_
#define TVAROMETR_ORCHESTRATOR__CENTRE_FACE_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/time.hpp"
#include "tvarometr_interfaces/action/centre_face.hpp"
#include "tvarometr_orchestrator/pose_array_from_string.hpp"

namespace tvarometr_orchestrator
{

/// Has the centring node frame the visitor's face before the models look at it.
///
/// The goal carries the photo pose the robot has just driven to, because the
/// centring node works every move out from it and never reads where the arm
/// actually is. Only Z changes, inside that node's own limits.
///
/// SUCCESS also covers a scan that ran into a Z limit with the face still off
/// target - the face is in the frame, which is what the analysis needs.
class CentreFace : public BT::RosActionNode<tvarometr_interfaces::action::CentreFace>
{
public:
  CentreFace(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<tvarometr_interfaces::action::CentreFace>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  BT::NodeStatus onFeedback(const std::shared_ptr<const Feedback> feedback) override;

  // The overload that also carries the result, because an aborted scan says why
  // in its message. Pulled in by name so the other overload is not hidden.
  using BT::RosActionNode<tvarometr_interfaces::action::CentreFace>::onFailure;
  BT::NodeStatus onFailure(
    BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result) override;

private:
  // A scan reports every step and every frame it waits through. Progress is
  // written at most every couple of seconds, like the motion node's.
  rclcpp::Time last_progress_log_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__CENTRE_FACE_HPP_
