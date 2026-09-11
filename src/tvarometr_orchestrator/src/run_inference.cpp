#include "tvarometr_orchestrator/run_inference.hpp"

namespace tvarometr_orchestrator
{

BT::PortsList RunInference::providedPorts()
{
  return providedBasicPorts(
    {BT::OutputPort<tvarometr_interfaces::msg::FaceAttributes>(
        "attributes", "Age, gender, emotion, and where the face sat in the frame")});
}

bool RunInference::setGoal(Goal & /*goal*/)
{
  return true;
}

BT::NodeStatus RunInference::onResultReceived(const WrappedResult & result)
{
  if (!result.result->success) {
    RCLCPP_ERROR(logger(), "Inference failed: %s", result.result->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  setOutput("attributes", result.result->attributes);
  RCLCPP_INFO(logger(), "Inference: %s", result.result->message.c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus RunInference::onFailure(BT::ActionNodeErrorCode error)
{
  RCLCPP_ERROR(logger(), "Inference action failed: %s", BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
