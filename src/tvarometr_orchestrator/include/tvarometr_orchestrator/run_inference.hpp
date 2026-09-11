#ifndef TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_
#define TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_

#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "tvarometr_interfaces/action/run_inference.hpp"

namespace tvarometr_orchestrator
{

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

  static BT::PortsList providedPorts();

  bool setGoal(Goal & goal) override;

  BT::NodeStatus onResultReceived(const WrappedResult & result) override;

  BT::NodeStatus onFailure(BT::ActionNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_
