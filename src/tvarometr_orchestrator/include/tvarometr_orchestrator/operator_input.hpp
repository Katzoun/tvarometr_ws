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

/// What the operator asks for, as flags the keyboard thread sets.
///
/// `abort` latches: E raises it, only Q lowers it, so S after a stop does nothing.
struct OperatorInput
{
  std::atomic<bool> start{false};
  // C. Not `continue`, which is a keyword.
  std::atomic<bool> proceed{false};
  std::atomic<bool> abort{false};
};

/// Reads S, C, E and Q without Enter until ROS shuts down, in its own thread.
///
/// Refuses S and C while an abort is latched, so the tree only checks the guard.
void readKeyboard(OperatorInput * input, rclcpp::Logger logger);

/// Fails from E until Q. At the top of a ReactiveSequence it halts the running
/// step - an orderly stop, since the driver runs out its queue.
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

/// Holds the tree until one key; registered as WaitForStart and WaitForContinue.
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
