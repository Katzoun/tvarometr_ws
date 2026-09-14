#include "tvarometr_orchestrator/robot_request.hpp"

#include <string>
#include <vector>

namespace tvarometr_orchestrator
{

BT::PortsList RobotRequest::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<std::string>("command", "One of the driver's commands, e.g. make_robot_ready"),
      BT::InputPort<std::vector<std::string>>(
        "params", "name=value pairs separated by ';', e.g. speed_ratio=20")});
}

bool RobotRequest::setRequest(Request::SharedPtr & request)
{
  const auto command = getInput<std::string>("command");
  if (!command) {
    RCLCPP_ERROR(logger(), "RobotRequest is missing its command port: %s", command.error().c_str());
    return false;
  }
  request->command = command.value();

  // Most commands take none, so leaving the port out means an empty list rather
  // than a mistake.
  const auto params = getInput<std::vector<std::string>>("params");
  if (params) {
    request->params = params.value();
  }
  return true;
}

BT::NodeStatus RobotRequest::onResponseReceived(const Response::SharedPtr & response)
{
  if (!response->status) {
    RCLCPP_ERROR(
      logger(), "Robot refused: %s (status %d)", response->message.c_str(),
      response->status_code);
    return BT::NodeStatus::FAILURE;
  }
  RCLCPP_INFO(logger(), "Robot: %s", response->message.c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus RobotRequest::onFailure(BT::ServiceNodeErrorCode error)
{
  RCLCPP_ERROR(logger(), "Robot request failed: %s", BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
