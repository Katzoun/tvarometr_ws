#ifndef TVAROMETR_ORCHESTRATOR__GENERATE_TRAJECTORIES_HPP_
#define TVAROMETR_ORCHESTRATOR__GENERATE_TRAJECTORIES_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "geometry_msgs/msg/pose_array.hpp"
#include "tvarometr_interfaces/srv/generate_trajectories.hpp"
#include "tvarometr_orchestrator/pose_array_from_string.hpp"

namespace tvarometr_orchestrator
{

/// Turns the attributes into the label, value and erase paths.
///
/// All three go to the blackboard; which get drawn is the tree's decision.
class GenerateTrajectories
  : public BT::RosServiceNode<tvarometr_interfaces::srv::GenerateTrajectories>
{
public:
  GenerateTrajectories(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosServiceNode<tvarometr_interfaces::srv::GenerateTrajectories>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setRequest(Request::SharedPtr & request) override;

  BT::NodeStatus onResponseReceived(const Response::SharedPtr & response) override;

  BT::NodeStatus onFailure(BT::ServiceNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__GENERATE_TRAJECTORIES_HPP_
