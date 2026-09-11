#include "tvarometr_orchestrator/lifecycle_nodes.hpp"

#include <optional>
#include <string>

#include "lifecycle_msgs/msg/state.hpp"
#include "lifecycle_msgs/msg/transition.hpp"

namespace tvarometr_orchestrator
{

namespace
{

/// The transitions a run needs, by the word the tree writes.
///
/// Empty for anything else, rather than a number that happens to be free: the
/// message numbers transitions from zero, so there is no spare value to mean
/// "not one of ours".
std::optional<uint8_t> transitionId(const std::string & name)
{
  using lifecycle_msgs::msg::Transition;
  if (name == "configure") {
    return Transition::TRANSITION_CONFIGURE;
  }
  if (name == "activate") {
    return Transition::TRANSITION_ACTIVATE;
  }
  if (name == "deactivate") {
    return Transition::TRANSITION_DEACTIVATE;
  }
  if (name == "cleanup") {
    return Transition::TRANSITION_CLEANUP;
  }
  return std::nullopt;
}

}  // namespace

BT::PortsList ChangeLifecycleState::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<std::string>(
        "transition", "configure, activate, deactivate or cleanup")});
}

bool ChangeLifecycleState::setRequest(Request::SharedPtr & request)
{
  const auto transition = getInput<std::string>("transition");
  if (!transition) {
    RCLCPP_ERROR(
      logger(), "ChangeLifecycleState is missing its transition port: %s",
      transition.error().c_str());
    return false;
  }

  const auto id = transitionId(transition.value());
  if (!id) {
    RCLCPP_ERROR(logger(), "Not a transition this tree knows: %s", transition.value().c_str());
    return false;
  }

  request->transition.id = *id;
  return true;
}

BT::NodeStatus ChangeLifecycleState::onResponseReceived(const Response::SharedPtr & response)
{
  if (!response->success) {
    // The node itself logged why. All that arrives here is that it refused,
    // which is also what a transition from the wrong state looks like.
    RCLCPP_ERROR(logger(), "%s refused the transition", service_name_.c_str());
    return BT::NodeStatus::FAILURE;
  }
  RCLCPP_INFO(logger(), "%s done", name().c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus ChangeLifecycleState::onFailure(BT::ServiceNodeErrorCode error)
{
  RCLCPP_ERROR(
    logger(), "%s could not be reached: %s", service_name_.c_str(), BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

BT::PortsList IsNodeActive::providedPorts()
{
  return providedBasicPorts({});
}

bool IsNodeActive::setRequest(Request::SharedPtr & /*request*/)
{
  // GetState asks nothing - the service name is the whole question.
  return true;
}

BT::NodeStatus IsNodeActive::onResponseReceived(const Response::SharedPtr & response)
{
  if (response->current_state.id == lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
    return BT::NodeStatus::SUCCESS;
  }
  RCLCPP_WARN(
    logger(), "%s is %s, not active", service_name_.c_str(),
    response->current_state.label.c_str());
  return BT::NodeStatus::FAILURE;
}

BT::NodeStatus IsNodeActive::onFailure(BT::ServiceNodeErrorCode error)
{
  RCLCPP_WARN(
    logger(), "%s could not be reached: %s", service_name_.c_str(), BT::toStr(error));
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
