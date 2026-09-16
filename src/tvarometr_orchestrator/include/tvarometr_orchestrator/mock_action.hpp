// Scaffolding: stands in for the steps that are not written yet, so the shape
// of the tree can be designed and exercised before any of them exist.

#ifndef TVAROMETR_ORCHESTRATOR__MOCK_ACTION_HPP_
#define TVAROMETR_ORCHESTRATOR__MOCK_ACTION_HPP_

#include <chrono>
#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// Stands in for an unwritten step: RUNNING for duration_ms, then `succeed`.
class MockAction : public BT::StatefulActionNode
{
public:
  MockAction(const std::string & name, const BT::NodeConfig & config, rclcpp::Logger logger)
  : BT::StatefulActionNode(name, config), logger_(logger)
  {
  }

  static BT::PortsList providedPorts();

  BT::NodeStatus onStart() override;

  BT::NodeStatus onRunning() override;

  void onHalted() override;

private:
  rclcpp::Logger logger_;
  std::chrono::steady_clock::time_point deadline_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__MOCK_ACTION_HPP_
