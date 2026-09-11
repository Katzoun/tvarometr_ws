#include "tvarometr_orchestrator/operator_input.hpp"

#include <termios.h>
#include <unistd.h>

namespace tvarometr_orchestrator
{

void readKeyboard(OperatorInput * input, rclcpp::Logger logger)
{
  termios original{};
  if (tcgetattr(STDIN_FILENO, &original) != 0) {
    RCLCPP_WARN(logger, "Not a terminal - S and E will not be read");
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

/// A key pressed while the last cycle was running is not a request for another.
BT::NodeStatus WaitForStart::onStart()
{
  input_->start = false;
  return BT::NodeStatus::RUNNING;
}

BT::NodeStatus WaitForStart::onRunning()
{
  if (!input_->start) {
    return BT::NodeStatus::RUNNING;
  }
  input_->start = false;
  // Nothing to clear: the keyboard refuses to raise `start` while the abort is
  // latched, so arriving here already means the guard is clear.
  return BT::NodeStatus::SUCCESS;
}

}  // namespace tvarometr_orchestrator
