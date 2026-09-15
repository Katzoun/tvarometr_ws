#include "tvarometr_orchestrator/move_to_joints.hpp"

#include <cmath>
#include <string>
#include <vector>

namespace tvarometr_orchestrator
{

BT::PortsList MoveToJoints::providedPorts()
{
  return providedBasicPorts(
    {BT::InputPort<std::vector<double>>(
        "joints_deg", "Axes 1 to 6 in degrees, separated by ';'"),
      BT::InputPort<std::string>(
        "motion_command", "MoveAbsJ", "MoveAbsJ, or MoveAbsL for a straight line"),
      BT::InputPort<std::string>("speed", "100", "TCP speed in mm/s"),
      BT::InputPort<std::string>("tool", "", "tooldata name; empty leaves it to RAPID"),
      BT::InputPort<std::string>("wobj", "", "wobjdata name; empty is wobj0")});
}

bool MoveToJoints::setGoal(Goal & goal)
{
  const auto joints_deg = getInput<std::vector<double>>("joints_deg");
  const auto motion_command = getInput<std::string>("motion_command");
  const auto speed = getInput<std::string>("speed");
  const auto tool = getInput<std::string>("tool");
  const auto wobj = getInput<std::string>("wobj");
  if (!joints_deg || !motion_command || !speed || !tool || !wobj) {
    RCLCPP_ERROR(logger(), "MoveToJoints cannot read its ports - check the tree file");
    return false;
  }
  if (joints_deg->size() != 6) {
    RCLCPP_ERROR(logger(), "MoveToJoints wants six axes, got %zu", joints_deg->size());
    return false;
  }

  // The message is radians, like the rest of ROS; the driver turns it back into
  // degrees for RAPID.
  const auto & deg = joints_deg.value();
  robot_control_msgs::msg::RobotJoints joints;
  joints.j1 = deg[0] * M_PI / 180.0;
  joints.j2 = deg[1] * M_PI / 180.0;
  joints.j3 = deg[2] * M_PI / 180.0;
  joints.j4 = deg[3] * M_PI / 180.0;
  joints.j5 = deg[4] * M_PI / 180.0;
  joints.j6 = deg[5] * M_PI / 180.0;

  goal.waypoints = {joints};
  goal.motion_command = motion_command.value();
  goal.speed = speed.value();
  goal.tool = tool.value();
  goal.wobj = wobj.value();

  RCLCPP_INFO(
    logger(), "Moving to [%.1f, %.1f, %.1f, %.1f, %.1f, %.1f] deg, %s at %s mm/s",
    deg[0], deg[1], deg[2], deg[3], deg[4], deg[5], goal.motion_command.c_str(),
    goal.speed.c_str());
  return true;
}

BT::NodeStatus MoveToJoints::onResultReceived(const WrappedResult & result)
{
  if (!result.result->success) {
    RCLCPP_ERROR(logger(), "Pose not reached: %s", result.result->message.c_str());
    return BT::NodeStatus::FAILURE;
  }
  return BT::NodeStatus::SUCCESS;
}

BT::NodeStatus MoveToJoints::onFailure(
  BT::ActionNodeErrorCode error, const std::optional<WrappedResult> & result)
{
  if (result && result->result) {
    RCLCPP_ERROR(
      logger(), "Joint motion %s: %s", BT::toStr(error), result->result->message.c_str());
  } else {
    RCLCPP_ERROR(logger(), "Joint motion failed: %s", BT::toStr(error));
  }
  return BT::NodeStatus::FAILURE;
}

}  // namespace tvarometr_orchestrator
