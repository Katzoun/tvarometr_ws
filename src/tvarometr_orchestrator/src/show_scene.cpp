#include "tvarometr_orchestrator/show_scene.hpp"

namespace tvarometr_orchestrator
{

BT::PortsList ShowScene::providedPorts()
{
  return providedBasicPorts({BT::InputPort<bool>("show", "true shows the scene, false blanks it")});
}

bool ShowScene::setRequest(Request::SharedPtr & request)
{
  const auto show = getInput<bool>("show");
  if (!show) {
    RCLCPP_ERROR(logger(), "ShowScene is missing its show port: %s", show.error().c_str());
    return false;
  }
  request->data = show.value();
  return true;
}

BT::NodeStatus ShowScene::onResponseReceived(const Response::SharedPtr & response)
{
  return response->success ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

BT::NodeStatus ShowScene::onFailure(BT::ServiceNodeErrorCode error)
{
  RCLCPP_ERROR(logger(), "ShowScene failed: %s", BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
