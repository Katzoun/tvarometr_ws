// Driving and checking the managed nodes the run depends on.
//
// Which node either one talks to is the `service_name` port, so one registered
// type serves the inference node, the drawing node and the robot driver alike.

#ifndef TVAROMETR_ORCHESTRATOR__LIFECYCLE_NODES_HPP_
#define TVAROMETR_ORCHESTRATOR__LIFECYCLE_NODES_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "lifecycle_msgs/srv/change_state.hpp"
#include "lifecycle_msgs/srv/get_state.hpp"

namespace tvarometr_orchestrator
{

/// Takes one managed node through one lifecycle transition.
///
/// The transition is a word rather than the number the message holds, so the
/// tree reads as an instruction: transition="configure".
///
/// Configure on the inference node loads half a gigabyte of weights and the
/// service does not answer until it is done, so this wants a timeout in minutes
/// - the library defaults to one second. That is set where it is registered.
class ChangeLifecycleState : public BT::RosServiceNode<lifecycle_msgs::srv::ChangeState>
{
public:
  ChangeLifecycleState(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosServiceNode<lifecycle_msgs::srv::ChangeState>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setRequest(Request::SharedPtr & request) override;

  BT::NodeStatus onResponseReceived(const Response::SharedPtr & response) override;

  BT::NodeStatus onFailure(BT::ServiceNodeErrorCode error) override;
};

/// Succeeds while a managed node reports itself active.
///
/// Despite the name this is a service call, not a cheap predicate: it returns
/// RUNNING until the answer arrives. It belongs in a plain Sequence, once per
/// cycle. In a reactive branch - next to IsAbortClear, say - it would send a
/// fresh request on every tick.
class IsNodeActive : public BT::RosServiceNode<lifecycle_msgs::srv::GetState>
{
public:
  IsNodeActive(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosServiceNode<lifecycle_msgs::srv::GetState>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setRequest(Request::SharedPtr & request) override;

  BT::NodeStatus onResponseReceived(const Response::SharedPtr & response) override;

  BT::NodeStatus onFailure(BT::ServiceNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__LIFECYCLE_NODES_HPP_
