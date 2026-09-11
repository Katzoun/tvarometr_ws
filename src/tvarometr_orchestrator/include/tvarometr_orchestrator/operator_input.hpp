// The operator's two keys, and the tree nodes that read them.
//
// Scaffolding: a terminal is the fastest way to drive a skeleton, but the real
// system gets a trigger that does not need somebody at a keyboard.

#ifndef TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_
#define TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_

#include <atomic>
#include <string>

#include "behaviortree_cpp/action_node.h"
#include "behaviortree_cpp/condition_node.h"
#include "rclcpp/rclcpp.hpp"

namespace tvarometr_orchestrator
{

/// What the operator is asking for, as two flags the keyboard thread sets.
///
/// `abort` latches: E raises it and only Q lowers it again. Leaning on S after
/// a stop does nothing, which is the whole point - somebody has to look at the
/// cell and say it is clear before the arm moves again.
struct OperatorInput
{
  std::atomic<bool> start{false};
  std::atomic<bool> abort{false};
};

/// Reads S, E and Q from the terminal until ROS shuts down.
///
/// S asks for a run, E stops one, Q acknowledges a stop. Refusing S while the
/// abort is latched happens here rather than in the tree: the tree only ever
/// asks whether the guard is clear, and this is what keeps it that simple.
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

/// Holds the cycle until the operator presses S.
class WaitForStart : public BT::StatefulActionNode
{
public:
  WaitForStart(const std::string & name, const BT::NodeConfig & config, OperatorInput * input)
  : BT::StatefulActionNode(name, config), input_(input)
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
  OperatorInput * input_;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__OPERATOR_INPUT_HPP_
