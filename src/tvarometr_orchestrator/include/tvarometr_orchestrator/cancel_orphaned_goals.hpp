// A goal whose send timed out can still reach the server and be accepted - and
// then the robot moves with nothing in the tree watching it. behaviortree_ros2
// only reports the timeout, so the nodes that move the robot call this.

#ifndef TVAROMETR_ORCHESTRATOR__CANCEL_ORPHANED_GOALS_HPP_
#define TVAROMETR_ORCHESTRATOR__CANCEL_ORPHANED_GOALS_HPP_

#include "behaviortree_ros2/bt_action_node.hpp"
#include "rclcpp/logging.hpp"
#include "rclcpp_action/client.hpp"

namespace tvarometr_orchestrator
{

/// After a send timeout, asks the server to cancel every goal it holds on this
/// action. Every goal and not only ours, because the one that timed out has no
/// handle to cancel it by - and while the tree waits on this action, nothing
/// else should be running on it anyway.
///
/// Covers a goal the server accepted while this client was not reading its
/// answer. A server stalled for so long that it accepts only after the cancel
/// has arrived is not covered.
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
