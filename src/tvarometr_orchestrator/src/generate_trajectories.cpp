#include "tvarometr_orchestrator/generate_trajectories.hpp"

namespace tvarometr_orchestrator
{

BT::PortsList GenerateTrajectories::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<tvarometr_interfaces::msg::FaceAttributes>(
        "attributes", "What the inference found"),
      BT::OutputPort<geometry_msgs::msg::PoseArray>(
        "labels", "The fixed column of labels, for a clean board"),
      BT::OutputPort<geometry_msgs::msg::PoseArray>(
        "values", "This run's answers, drawn every cycle"),
      BT::OutputPort<geometry_msgs::msg::PoseArray>(
        "erase", "The sweep across the value column")});
}

bool GenerateTrajectories::setRequest(Request::SharedPtr & request)
{
  const auto attributes = getInput<tvarometr_interfaces::msg::FaceAttributes>("attributes");
  if (!attributes) {
    RCLCPP_ERROR(
      logger(), "GenerateTrajectories is missing its attributes port: %s",
      attributes.error().c_str());
    return false;
  }
  request->attributes = attributes.value();
  return true;
}

BT::NodeStatus GenerateTrajectories::onResponseReceived(const Response::SharedPtr & response)
{
  if (!response->success) {
    RCLCPP_ERROR(logger(), "Trajectory generation failed: %s", response->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  setOutput("labels", response->labels);
  setOutput("values", response->values);
  setOutput("erase", response->erase);
  RCLCPP_INFO(logger(), "Trajectories: %s", response->message.c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus GenerateTrajectories::onFailure(BT::ServiceNodeErrorCode error)
{
  RCLCPP_ERROR(logger(), "Trajectory service failed: %s", BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
