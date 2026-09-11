#ifndef TVAROMETR_ORCHESTRATOR__GENERATE_DRAWING_HPP_
#define TVAROMETR_ORCHESTRATOR__GENERATE_DRAWING_HPP_

#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "geometry_msgs/msg/pose_array.hpp"
#include "tvarometr_interfaces/action/generate_drawing.hpp"

namespace tvarometr_orchestrator
{

/// Turns the analysis into the path the robot draws on the board.
///
/// The first node with an input port of its own: the attributes RunInference
/// left on the blackboard are what the goal carries.
class GenerateDrawing : public BT::RosActionNode<tvarometr_interfaces::action::GenerateDrawing>
{
public:
  GenerateDrawing(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosActionNode<tvarometr_interfaces::action::GenerateDrawing>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  BT::NodeStatus onFailure(BT::ActionNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__GENERATE_DRAWING_HPP_
