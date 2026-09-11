#include "tvarometr_orchestrator/generate_drawing.hpp"

namespace tvarometr_orchestrator
{

BT::PortsList GenerateDrawing::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<tvarometr_interfaces::msg::FaceAttributes>(
        "attributes", "What the inference found"),
      BT::OutputPort<geometry_msgs::msg::PoseArray>(
        "path", "The points to draw, pen down at z=0")});
}

bool GenerateDrawing::setGoal(Goal & goal)
{
  const auto attributes = getInput<tvarometr_interfaces::msg::FaceAttributes>("attributes");
  if (!attributes) {
    RCLCPP_ERROR(
      logger(), "GenerateDrawing is missing its attributes port: %s",
      attributes.error().c_str());
    return false;
  }
  goal.attributes = attributes.value();
  return true;
}

BT::NodeStatus GenerateDrawing::onResultReceived(const WrappedResult & result)
{
  if (!result.result->success) {
    RCLCPP_ERROR(logger(), "Drawing generation failed: %s", result.result->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  setOutput("path", result.result->path);
  RCLCPP_INFO(logger(), "Drawing: %s", result.result->message.c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus GenerateDrawing::onFailure(BT::ActionNodeErrorCode error)
{
  RCLCPP_ERROR(logger(), "Drawing action failed: %s", BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
