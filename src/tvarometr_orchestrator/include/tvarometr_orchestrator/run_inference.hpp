#ifndef TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_
#define TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_

#include <optional>
#include <string>

#include "behaviortree_ros2/bt_action_node.hpp"
#include "tvarometr_interfaces/action/run_inference.hpp"

namespace tvarometr_orchestrator
{

/// Asks the inference node to analyse the visitor; the answer goes to `attributes`.
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

  // The overload with the result, because an aborted goal says why in its message.
  using BT::RosActionNode<tvarometr_interfaces::action::RunInference>::onFailure;
  BT::NodeStatus onFailure(
    BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__RUN_INFERENCE_HPP_
