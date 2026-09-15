// The operator's keys, and the tree nodes that read them.

#ifndef TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_
#define TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_

#include <atomic>
#include <string>

#include "behaviortree_cpp/action_node.h"
#include "behaviortree_cpp/condition_node.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// What the operator is asking for, as flags the keyboard thread sets.
///
/// `abort` latches: E raises it and only Q lowers it again. Leaning on S after
/// a stop does nothing, which is the whole point - somebody has to look at the
/// cell and say it is clear before the arm moves again.
struct OperatorInput
{
  std::atomic<bool> start{false};
  // C. Not `continue`, which is a keyword.
  std::atomic<bool> proceed{false};
  std::atomic<bool> abort{false};
};

/// Reads S, C, E and Q from the terminal until ROS shuts down.
///
/// S asks for a run, C lets a paused one go on, E stops one, Q acknowledges a
/// stop. Refusing S and C while the abort is latched happens here rather than in
/// the tree: the tree only ever asks whether the guard is clear, and this is
/// what keeps it that simple.
///
/// Takes the terminal out of line mode, so a key registers without Enter, and
/// puts it back on the way out. Runs in its own thread because read() blocks
/// and the tree has ticking to do.
void readKeyboard(OperatorInput * input, rclcpp::Logger logger);

/// Fails once E has been pressed, and keeps failing until Q acknowledges it.
///
/// Belongs at the top of a ReactiveSequence, which re-ticks it on every pass
/// and halts the running step when it fails. That halt cancels a ROS action,
/// and cancelling a motion goal does NOT stop the arm - the queue runs to its
/// end. This is an orderly stop, not the robot's emergency stop.
class IsAbortClear : public BT::ConditionNode
{
public:
  IsAbortClear(const std::string & name, const BT::NodeConfig & config, OperatorInput * input)
  : BT::ConditionNode(name, config), input_(input)
  {
  }

  static BT::PortsList providedPorts()
  {
    return {};
  }

  BT::NodeStatus tick() override;

private:
  OperatorInput * input_;
};

/// Holds the tree until the operator presses one particular key.
///
/// Which key is the flag it is built with, so one class serves every pause:
/// registered once over `start` as WaitForStart and once over `proceed` as
/// WaitForContinue.
class WaitForKey : public BT::StatefulActionNode
{
public:
  WaitForKey(
    const std::string & name, const BT::NodeConfig & config, std::atomic<bool> * pressed)
  : BT::StatefulActionNode(name, config), pressed_(pressed)
  {
  }

  static BT::PortsList providedPorts()
  {
    return {};
  }

  BT::NodeStatus onStart() override;

  BT::NodeStatus onRunning() override;

  void onHalted() override
  {
  }

private:
  std::atomic<bool> * pressed_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_
