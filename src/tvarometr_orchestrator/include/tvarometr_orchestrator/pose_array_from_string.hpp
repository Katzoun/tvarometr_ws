// Lets a tree file spell a pose out by hand - the point the arm backs off to,
// say - instead of only passing along one another node produced.

#ifndef TVAROMETR_ORCHESTRATOR__POSE_ARRAY_FROM_STRING_HPP_
#define TVAROMETR_ORCHESTRATOR__POSE_ARRAY_FROM_STRING_HPP_

#include <string>

#include "behaviortree_cpp/basic_types.h"
#include "behaviortree_cpp/exceptions.h"
#include "geometry_msgs/msg/pose_array.hpp"

namespace BT
{

/// x,y,z,qx,qy,qz,qw per pose in metres, poses separated by ';'.
///
/// Include it in every header with a PoseArray port, or BT.CPP uses its throwing default.
template<>
inline geometry_msgs::msg::PoseArray convertFromString<geometry_msgs::msg::PoseArray>(
  StringView str)
{
  std::string text;
  for (const char c : str) {
    if (c != ' ') {
      text.push_back(c);
    }
  }

  geometry_msgs::msg::PoseArray path;
  for (const auto & pose_text : splitString(text, ';')) {
    const auto fields = splitString(pose_text, ',');
    if (fields.size() != 7) {
      throw RuntimeError("A pose is x,y,z,qx,qy,qz,qw, got '", std::string(pose_text), "'");
    }
    geometry_msgs::msg::Pose pose;
    pose.position.x = convertFromString<double>(fields[0]);
    pose.position.y = convertFromString<double>(fields[1]);
    pose.position.z = convertFromString<double>(fields[2]);
    pose.orientation.x = convertFromString<double>(fields[3]);
    pose.orientation.y = convertFromString<double>(fields[4]);
    pose.orientation.z = convertFromString<double>(fields[5]);
    pose.orientation.w = convertFromString<double>(fields[6]);
    path.poses.push_back(pose);
  }
  return path;
}

}  // namespace BT

#endif  // TVAROMETR_ORCHESTRATOR__POSE_ARRAY_FROM_STRING_HPP_
