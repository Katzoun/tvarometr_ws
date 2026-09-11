#ifndef TVAROMETR_ORCHESTRATOR__GENERATE_TRAJECTORIES_HPP_
#define TVAROMETR_ORCHESTRATOR__GENERATE_TRAJECTORIES_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "geometry_msgs/msg/pose_array.hpp"
#include "tvarometr_interfaces/srv/generate_trajectories.hpp"

namespace tvarometr_orchestrator
{

/// Turns the analysis into the paths the robot puts on the board.
///
/// The first node with an input port of its own: the attributes the inference
/// left on the blackboard are what the request carries.
///
/// All three paths arrive together and all three go onto the blackboard, even
/// though a given cycle draws only some of them. Which ones is the tree's
/// decision - a clean board takes the labels, every other run erases first -
/// and keeping that decision in the tree is what lets this node stay a
/// function: attributes in, geometry out, nothing remembered between calls.
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
