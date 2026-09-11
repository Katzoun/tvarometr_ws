#ifndef TVAROMETR_ORCHESTRATOR__LOG_MESSAGE_HPP_
#define TVAROMETR_ORCHESTRATOR__LOG_MESSAGE_HPP_

#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// Writes a line to the ROS log.
///
/// A tree needs at least one node of its own to be worth loading, and this is
/// the smallest one that is still useful - it stays handy for marking progress
/// once the real nodes are in.
class LogMessage : public BT::SyncActionNode
{
public:
  LogMessage(const std::string & name, const BT::NodeConfig & config, rclcpp::Logger logger)
  : BT::SyncActionNode(name, config), logger_(logger)
  {
  }

  static BT::PortsList providedPorts();

  BT::NodeStatus tick() override;

private:
  rclcpp::Logger logger_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__LOG_MESSAGE_HPP_
