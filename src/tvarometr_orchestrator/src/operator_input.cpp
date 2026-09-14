#include "tvarometr_orchestrator/operator_input.hpp"

#include <termios.h>
#include <unistd.h>

namespace tvarometr_orchestrator
{

void readKeyboard(OperatorInput * input, rclcpp::Logger logger)
{
  termios original{};
  if (tcgetattr(STDIN_FILENO, &original) != 0) {
    RCLCPP_WARN(logger, "Not a terminal - the operator keys will not be read");
    return;
  }

  termios raw = original;
  raw.c_lflag &= ~static_cast<tcflag_t>(ICANON | ECHO);
  raw.c_cc[VMIN] = 0;
  // A tenth of a second, so read() returns often enough to notice shutdown.
  raw.c_cc[VTIME] = 1;
  tcsetattr(STDIN_FILENO, TCSANOW, &raw);

  while (rclcpp::ok()) {
    char key = 0;
    if (read(STDIN_FILENO, &key, 1) != 1) {
      continue;
    }
    if (key == 's' || key == 'S') {
      if (input->abort) {
        RCLCPP_WARN(logger, "Still aborted - press Q to acknowledge before starting again");
      } else {
        input->start = true;
      }
    } else if (key == 'c' || key == 'C') {
      if (input->abort) {
        RCLCPP_WARN(logger, "Still aborted - press Q to acknowledge first");
      } else {
        input->proceed = true;
      }
    } else if (key == 'e' || key == 'E') {
      input->abort = true;
      RCLCPP_WARN(logger, "Abort requested - press Q to acknowledge");
    } else if (key == 'q' || key == 'Q') {
      if (input->abort) {
        input->abort = false;
        RCLCPP_INFO(logger, "Abort acknowledged");
      }
    }
  }

  tcsetattr(STDIN_FILENO, TCSANOW, &original);
}

BT::NodeStatus IsAbortClear::tick()
{
  return input_->abort ? BT::NodeStatus::FAILURE : BT::NodeStatus::SUCCESS;
}

/// A key pressed before the tree got here is not an answer to this pause - an
/// S hit during the last run, or a C hit while the robot was still drawing.
BT::NodeStatus WaitForKey::onStart()
{
  *pressed_ = false;
  return BT::NodeStatus::RUNNING;
}

BT::NodeStatus WaitForKey::onRunning()
{
  if (!*pressed_) {
    return BT::NodeStatus::RUNNING;
  }
  *pressed_ = false;
  // Nothing else to clear: the keyboard refuses to raise either flag while the
  // abort is latched, so arriving here already means the guard is clear.
  return BT::NodeStatus::SUCCESS;
}

}  // namespace tvarometr_orchestrator
