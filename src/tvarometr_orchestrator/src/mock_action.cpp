#include "tvarometr_orchestrator/mock_action.hpp"

#include <chrono>

namespace tvarometr_orchestrator
{

BT::PortsList MockAction::providedPorts()
{
  return {
    BT::InputPort<unsigned>("duration_ms", 1000, "How long to pretend to work"),
    BT::InputPort<bool>("succeed", true, "What to report once the time is up")};
}

BT::NodeStatus MockAction::onStart()
{
  const auto duration = std::chrono::milliseconds(getInput<unsigned>("duration_ms").value());
  deadline_ = std::chrono::steady_clock::now() + duration;
  RCLCPP_INFO(logger_, "%s: working", name().c_str());
  return BT::NodeStatus::RUNNING;
}

BT::NodeStatus MockAction::onRunning()
{
  if (std::chrono::steady_clock::now() < deadline_) {
    return BT::NodeStatus::RUNNING;
  }
  const bool succeed = getInput<bool>("succeed").value();
  RCLCPP_INFO(logger_, "%s: %s", name().c_str(), succeed ? "done" : "gave up");
  return succeed ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

void MockAction::onHalted()
{
  RCLCPP_WARN(logger_, "%s: halted", name().c_str());
}

}  // namespace tvarometr_orchestrator
