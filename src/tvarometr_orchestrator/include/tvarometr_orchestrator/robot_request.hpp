#ifndef TVAROMETR_ORCHESTRATOR__ROBOT_REQUEST_HPP_
#define TVAROMETR_ORCHESTRATOR__ROBOT_REQUEST_HPP_

#include <string>

#include "behaviortree_ros2/bt_service_node.hpp"
#include "robot_control_msgs/srv/robot_request_srv.hpp"

namespace tvarometr_orchestrator
{

/// Calls one command on the robot driver's controller_request service.
///
/// The driver keeps everything that is not a motion behind this one service,
/// named by a string - make_robot_ready, set_speedratio, run_rapid_routine and
/// the rest - so one node with a `command` port reaches all of it. The driver's
/// `help` command lists what there is.
class RobotRequest : public BT::RosServiceNode<robot_control_msgs::srv::RobotRequestSrv>
{
public:
  RobotRequest(
    const std::string & name, const BT::NodeConfig & config, const BT::RosNodeParams & params)
  : BT::RosServiceNode<robot_control_msgs::srv::RobotRequestSrv>(name, config, params)
  {
  }

  static BT::PortsList providedPorts();

  bool setRequest(Request::SharedPtr & request) override;

  BT::NodeStatus onResponseReceived(const Response::SharedPtr & response) override;

  BT::NodeStatus onFailure(BT::ServiceNodeErrorCode error) override;
};

}  // namespace tvarometr_orchestrator

#endif  // TVAROMETR_ORCHESTRATOR__ROBOT_REQUEST_HPP_
