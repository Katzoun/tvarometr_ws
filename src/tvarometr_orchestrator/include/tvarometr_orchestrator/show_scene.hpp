#ifndef TVAROMETR_ORCHESTRATOR__SHOW_SCENE_HPP_
#define TVAROMETR_ORCHESTRATOR__SHOW_SCENE_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "std_srvs/srv/set_bool.hpp"

namespace tvarometr_orchestrator
{

/// Turns the TV's scene image on or off on the inference node.
class ShowScene : public BT::RosServiceNode<std_srvs::srv::SetBool>
{
public:
  ShowScene(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosServiceNode<std_srvs::srv::SetBool>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setRequest(Request::SharedPtr & request) override;

  BT::NodeStatus onResponseReceived(const Response::SharedPtr & response) override;

  BT::NodeStatus onFailure(BT::ServiceNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__SHOW_SCENE_HPP_
