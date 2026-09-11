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

/// Stands in for a step that is not written yet.
///
/// Reports RUNNING for duration_ms and then whatever `succeed` says, which is
/// what makes the failure branches of the tree testable before anything real
/// can fail.
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
