#ifndef TVAROMETR_ORCHESTRATOR__LOG_MESSAGE_HPP_
#define TVAROMETR_ORCHESTRATOR__LOG_MESSAGE_HPP_

#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// Writes a line to the ROS log.
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
