#include "tvarometr_orchestrator/centre_face.hpp"

#include <memory>
#include <string>

#include "tvarometr_orchestrator/cancel_orphaned_goals.hpp"

namespace tvarometr_orchestrator
{

BT::PortsList CentreFace::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<geometry_msgs::msg::PoseArray>(
        "photo_pose", "Where the robot already stands, one pose in the wobj below"),
      // Same names as the motion nodes use: the camera rides on the flange, so
      // the scan moves whatever tool is fitted.
      BT::InputPort<std::string>("tool", "", "tooldata name, e.g. tooltuzka"),
      BT::InputPort<std::string>("wobj", "", "wobjdata name, e.g. wobjtabletop")});
}

bool CentreFace::setGoal(Goal & goal)
{
  const auto photo_pose = getInput<geometry_msgs::msg::PoseArray>("photo_pose");
  const auto tool = getInput<std::string>("tool");
  const auto wobj = getInput<std::string>("wobj");
  if (!photo_pose || !tool || !wobj) {
    RCLCPP_ERROR(logger(), "CentreFace cannot read its ports - check the tree file");
    return false;
  }
  if (photo_pose->poses.size() != 1) {
    RCLCPP_ERROR(
      logger(), "CentreFace wants one photo pose, got %zu", photo_pose->poses.size());
    return false;
  }

  goal.photo_pose = photo_pose->poses.front();
  goal.tool = tool.value();
  goal.wobj = wobj.value();

  RCLCPP_INFO(
    logger(), "Framing the visitor from z %.3f m, tool '%s', wobj '%s'",
    goal.photo_pose.position.z, goal.tool.c_str(), goal.wobj.c_str());
  last_progress_log_ = now();
  return true;
}

BT::NodeStatus CentreFace::onFeedback(const std::shared_ptr<const Feedback> feedback)
{
  const auto stamp = now();
  if ((stamp - last_progress_log_).seconds() >= 2.0) {
    RCLCPP_INFO(
      logger(), "Step %u: %s, %+.0f px off, z %.3f", feedback->step,
      feedback->state.c_str(), feedback->error_px, feedback->z);
    last_progress_log_ = stamp;
  }
  return BT::NodeStatus::RUNNING;
}

BT::NodeStatus CentreFace::onResultReceived(const WrappedResult & result)
{
  if (!result.result->success) {
    RCLCPP_ERROR(logger(), "Not framed: %s", result.result->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  if (result.result->at_limit) {
    RCLCPP_WARN(
      logger(), "Framed as well as the Z limits allow: %s", result.result->message.c_str());
  } else {
    RCLCPP_INFO(logger(), "Framed: %s", result.result->message.c_str());
  }
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus CentreFace::onFailure(
  BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result)
{
  cancelOrphanedGoals(error, *client_instance_->action_client, logger());

  // A rejected goal has no result: the photo pose was outside the Z limits, or
  // the limits themselves are the wrong way round. The centring node logged it.
  if (result && result->result) {
    RCLCPP_ERROR(
      logger(), "Centring %s: %s", BT::toStr(error), result->result->message.c_str());
  } else {
    RCLCPP_ERROR(logger(), "Centring failed: %s", BT::toStr(error));
  }
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
