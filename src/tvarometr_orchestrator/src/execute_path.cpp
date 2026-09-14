#include "tvarometr_orchestrator/execute_path.hpp"

#include <memory>
#include <string>

namespace tvarometr_orchestrator
{

BT::PortsList ExecutePath::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<geometry_msgs::msg::PoseArray>(
        "path", "Poses in metres, in the board's frame"),
      BT::InputPort<std::string>(
        "motion_command", "MoveL", "Which RAPID routine drives it: MoveL or MoveJ"),
      // Text, because that is what the goal carries. RAPID clamps it to 5-1000.
      BT::InputPort<std::string>("speed", "100", "TCP speed in mm/s"),
      // Names of data on the controller. Empty leaves the choice to RAPID -
      // whichever tool it last used, and wobj0, the robot's base. The pen and
      // the eraser share one flange, so which of them touches the board is only
      // ever this tool name.
      BT::InputPort<std::string>("tool", "", "tooldata name, e.g. tooltuzka"),
      BT::InputPort<std::string>("wobj", "", "wobjdata name, e.g. wobjtabletop")});
}

bool ExecutePath::setGoal(Goal & goal)
{
  const auto path = getInput<geometry_msgs::msg::PoseArray>("path");
  const auto motion_command = getInput<std::string>("motion_command");
  const auto speed = getInput<std::string>("speed");
  const auto tool = getInput<std::string>("tool");
  const auto wobj = getInput<std::string>("wobj");
  if (!path || !motion_command || !speed || !tool || !wobj) {
    RCLCPP_ERROR(logger(), "ExecutePath cannot read its ports - check the tree file");
    return false;
  }

  goal.path = path.value();
  goal.motion_command = motion_command.value();
  goal.speed = speed.value();
  goal.tool = tool.value();
  goal.wobj = wobj.value();

  RCLCPP_INFO(
    logger(), "Sending %zu poses, %s at %s mm/s, tool '%s', wobj '%s'",
    goal.path.poses.size(), goal.motion_command.c_str(), goal.speed.c_str(),
    goal.tool.c_str(), goal.wobj.c_str());
  last_progress_log_ = now();
  return true;
}

BT::NodeStatus ExecutePath::onFeedback(const std::shared_ptr<const Feedback> feedback)
{
  const auto stamp = now();
  if ((stamp - last_progress_log_).seconds() >= 2.0) {
    RCLCPP_INFO(logger(), "Robot: %s", feedback->state.c_str());
    last_progress_log_ = stamp;
  }
  return BT::NodeStatus::RUNNING;
}

BT::NodeStatus ExecutePath::onResultReceived(const WrappedResult & result)
{
  if (!result.result->success) {
    RCLCPP_ERROR(logger(), "Path not driven: %s", result.result->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  RCLCPP_INFO(
    logger(), "Path driven: %d points - %s", result.result->executed_count,
    result.result->message.c_str());
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus ExecutePath::onFailure(
  BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result)
{
  // A rejected goal has no result; the driver logged its reason on its side -
  // not active, not idle, or already busy with another path.
  if (result && result->result) {
    RCLCPP_ERROR(
      logger(), "Motion %s after %d points: %s", BT::toStr(error),
      result->result->executed_count, result->result->message.c_str());
  } else {
    RCLCPP_ERROR(logger(), "Motion failed: %s", BT::toStr(error));
  }
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
