// A goal whose send timed out may still be accepted, and the robot would move
// unwatched. behaviortree_ros2 only reports the timeout.

#ifndef TVAROMETR_ORCHESTRATOR__CANCEL_ORPHANED_GOALS_HPP_
#define TVAROMETR_ORCHESTRATOR__CANCEL_ORPHANED_GOALS_HPP_

#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/logging.hpp"
#include "rclcpp_action/client.hpp"

namespace tvarometr_orchestrator
{

/// After a send timeout, cancels every goal on the action: the lost one has no
/// handle, and nothing else should run there meanwhile. A server that accepts
/// only after the cancel arrives is not covered.
template<typename ActionT>
void cancelOrphanedGoals(
  BT::ActionNodeErrorCode error, rclcpp_action::Client<ActionT> & client,
  const rclcpp::Logger & logger)
{
  if (error != BT::SEND_GOAL_TIMEOUT) {
    return;
  }
  RCLCPP_WARN(
    logger, "Cancelling every goal on this action, in case the one that timed out got through");
  static_cast<void>(client.async_cancel_all_goals());
}

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__CANCEL_ORPHANED_GOALS_HPP_
