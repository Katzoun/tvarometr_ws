#include "tvarometr_orchestrator/mock_inference.hpp"

#include <string>

namespace tvarometr_orchestrator
{

BT::PortsList MockInference::providedPorts()
{
  // The defaults are what a run uses unless the tree file says otherwise, so a
  // different face is a different attribute in the XML and no rebuild.
  return {
    BT::InputPort<int>("age", 32, "Years"),
    BT::InputPort<std::string>("gender", "male", "The model's own label: male or female"),
    BT::InputPort<std::string>(
      "emotion", "happiness", "The model's own label: neutral, happiness, sadness, ..."),
    BT::OutputPort<tvarometr_interfaces::msg::FaceAttributes>(
      "attributes", "What RunInference would have found")};
}

BT::NodeStatus MockInference::tick()
{
  const auto age = getInput<int>("age");
  const auto gender = getInput<std::string>("gender");
  const auto emotion = getInput<std::string>("emotion");
  if (!age || !gender || !emotion) {
    RCLCPP_ERROR(logger_, "MockInference cannot read its ports - check the tree file");
    return BT::NodeStatus::FAILURE;
  }

  tvarometr_interfaces::msg::FaceAttributes attributes;
  attributes.age = age.value();
  attributes.gender = gender.value();
  attributes.emotion = emotion.value();
  attributes.emotion_confidence = 1.0F;
  // The bounding box and the image size stay zero. What reads them is the
  // approach move, and that is still a MockAction - inventing a plausible box
  // here would only be a number waiting to be believed.

  setOutput("attributes", attributes);
  RCLCPP_INFO(
    logger_, "Pretending the camera saw: %d, %s, %s", attributes.age,
    attributes.gender.c_str(), attributes.emotion.c_str());
  return BT::NodeStatus::SUCCESS;
}

}  // namespace tvarometr_orchestrator
