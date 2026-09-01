"""Names and constants shared between nodes.

Carried over from the diploma project's core_pkg/systemconstants.py, trimmed to
what tvarometr actually uses. The node state names that used to live here are
gone - nodes are ROS 2 managed nodes now, so lifecycle_msgs owns that vocabulary.
"""

# How long a synchronous service call waits before giving up.
CALL_TIMEOUT_SEC = 30.0


class RobotControllerConstants:
    """Names on the ROS side, and the RAPID symbols/routines they map to.

    Modules, Symbols and States have to match the RAPID program running on the
    controller. Routines are the default names only - the node takes them as
    parameters so the RAPID side can keep its own naming.
    """

    NODE_NAME = "robot_controller"

    class ServiceNames:
        CONTROLLER_REQUEST = "controller_request"

    class TopicNames:
        JOINT_STATES_TOPIC = "joint_states"

    class ActionNames:
        ROBOT_ROBTARGET_MOVE_ACTION = "robot_robtarget_move"
        ROBOT_JOINTTARGET_MOVE_ACTION = "robot_jointtarget_move"

    class MotionCommands:
        MOVE_L = "MoveL"
        MOVE_J = "MoveJ"
        MOVE_ABS_J = "MoveAbsJ"
        MOVE_ABS_L = "MoveAbsL"

    class Modules:
        RAPID = "TRobRAPID"
        USER = "TRobUser"
        MAIN = "TRobMain"

    class Symbols:
        ROUTINE_NAME = "routine_name_input"
        SPEED = "speednum"
        CURRENT_STATE = "current_state"
        RECEIVED_ROBTARGET = "received_robtarget"

    class States:
        EXECUTE = "2"
        IDLE = "0"

    class Routines:
        MOVE_L = "run_routine_buffer_moveL"
        MOVE_J = "run_routine_buffer_moveJ"
        MOVE_ABS_J = "run_routine_buffer_moveabsJ"
        MOVE_ABS_L = "run_routine_buffer_moveabsL"
        SINGLE_MOVE_L = "run_single_moveL"
        SINGLE_MOVE_J = "run_single_moveJ"
        SINGLE_MOVE_C = "run_single_moveC"
