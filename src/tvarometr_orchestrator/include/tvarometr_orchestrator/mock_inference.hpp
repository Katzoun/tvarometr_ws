// Scaffolding: stands in for the inference stack, so the steps after it can be
// built and watched without a camera or a GPU.

#ifndef TVAROMETR_ORCHESTRATOR__MOCK_INFERENCE_HPP_
#define TVAROMETR_ORCHESTRATOR__MOCK_INFERENCE_HPP_

#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"
#include "tvarometr_interfaces/msg/face_attributes.hpp"

namespace tvarometr_orchestrator
{

/// Puts made-up attributes on the same port RunInference would.
class MockInference : public BT::SyncActionNode
{
public:
  MockInference(const std::string & name, const BT::NodeConfig & config, rclcpp::Logger logger)
  : BT::SyncActionNode(name, config), logger_(logger)
  {
  }

  static BT::PortsList providedPorts();

  BT::NodeStatus tick() override;

private:
  rclcpp::Logger logger_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__MOCK_INFERENCE_HPP_
