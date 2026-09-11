#include "tvarometr_orchestrator/log_message.hpp"

#include <string>

namespace tvarometr_orchestrator
{

BT::PortsList LogMessage::providedPorts()
{
  return {BT::InputPort<std::string>("message", "What to write to the log")};
}

BT::NodeStatus LogMessage::tick()
{
  const auto message = getInput<std::string>("message");
  if (!message) {
    RCLCPP_ERROR(
      logger_, "LogMessage is missing its message port: %s",
      message.error().c_str());
    return BT::NodeStatus::FAILURE;
  }
  RCLCPP_INFO(logger_, "%s", message.value().c_str());
  return BT::NodeStatus::SUCCESS;
}

}  // namespace tvarometr_orchestrator
