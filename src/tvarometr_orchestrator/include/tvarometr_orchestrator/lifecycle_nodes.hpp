// Driving and checking the managed nodes; `service_name` says which one.

#ifndef TVAROMETR_ORCHESTRATOR__LIFECYCLE_NODES_HPP_
#define TVAROMETR_ORCHESTRATOR__LIFECYCLE_NODES_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "lifecycle_msgs/srv/change_state.hpp"
#include "lifecycle_msgs/srv/get_state.hpp"

namespace tvarometr_orchestrator
{

/// Takes one managed node through one transition, named by a word.
///
/// Configuring the inference node takes minutes; the timeout is set at registration.
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
/// A service call, so once per cycle - not in a reactive branch, which re-ticks it.
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
