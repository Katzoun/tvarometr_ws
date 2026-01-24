import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

import rclpy
from rclpy.node import Node
import std_msgs.msg as std_msgs
from geometry_msgs.msg import Point
import time

from utils.state_machine import StateMachine, RobotState
from  utils.rwsprovider import RWSClient
from utils.rwswrappers import RWSWrappers
import utils.rwsutils as rwsutils
import utils.path_generator_multiline as path_generator
from utils.exceptions import RWSException
import numpy as np
import json

#simulator
#robotIP = "192.168.0.30"
# robot_port = 80

#real 
robotIP = "192.168.0.37"
robot_port = 443

username = "Admin"
password = "robotics"




class MasterNode(Node):

    def __init__(self):
        super().__init__('master_node')

        #variables
        self.points = []
        self.current_key = None
        self.current_inference_result = None
        self.rapid_ready = False

        self.task_timeout = 30.0  # seconds
        self.iter = 0

        # Parameters
        self.useRWS = True  # Default to using RWS
        self.generate_csv = True  # Default to generating CSV files

        # Load parameters from ROS2 parameter server
        self.declare_parameter('use_rws', self.useRWS)
        self.declare_parameter('generate_csv', self.generate_csv)
        self.useRWS = self.get_parameter('use_rws').get_parameter_value().bool_value
        self.generate_csv = self.get_parameter('generate_csv').get_parameter_value().bool_value

        self.get_logger().info(f'Using RWS: {self.useRWS}, Generate CSV: {self.generate_csv}')
        
        # ROS2 setup
        self.start_publisher = self.create_publisher(std_msgs.String, '/start_inference', 10)
        self.inference_listener = self.create_subscription(std_msgs.String, '/face_attributes',
            self.inference_callback, 10)
        self.keypress_listener = self.create_subscription(std_msgs.String, '/pressed_key',
            self.keypress_callback, 10)
        
        
        if not self.useRWS:
            self.point_publisher = self.create_publisher(Point, '/point_sim', 10)
            self.clear_turtle_publisher = self.create_publisher(std_msgs.Bool, '/clear_turtle', 10)
        else:
            self.get_logger().info('Connecting to RWS...')
            self.rws_client = RWSClient(robotIP, username, password, robot_port)
            self.rws_wrappers = RWSWrappers(self.rws_client)
        
        
        # State machine setup
        self.state_machine = StateMachine(RobotState.INIT)
        self.setup_state_machine()
        
        # Timer for state machine execution
        self.state_timer = self.create_timer(0.1, self.state_machine_callback)  # 10 Hz
        

    def setup_state_machine(self):
        """Configure the state machine transitions and handlers"""
        
        # Define state transitions
        self.state_machine.add_transition(RobotState.INIT, 'initialized', RobotState.IDLE)
        self.state_machine.add_transition(RobotState.IDLE, 'start_inference', RobotState.WAITING_FOR_INFERENCE)
        self.state_machine.add_transition(RobotState.WAITING_FOR_INFERENCE, 'inference_received', RobotState.PROCESSING_INFERENCE)
        self.state_machine.add_transition(RobotState.PROCESSING_INFERENCE, 'setup_robot', RobotState.SETTING_UP_ROBOT)
        self.state_machine.add_transition(RobotState.SETTING_UP_ROBOT, 'start_movement_sim', RobotState.DRAWING_SIM)
        self.state_machine.add_transition(RobotState.DRAWING_SIM, 'sim_task_completed', RobotState.IDLE)

        ## Real robot transitions
        self.state_machine.add_transition(RobotState.SETTING_UP_ROBOT, 'start_drawing_real', RobotState.DRAWING_REAL)
        self.state_machine.add_transition(RobotState.DRAWING_REAL, 'drawing_completed', RobotState.ERASING_AND_TC)
        # self.state_machine.add_transition(RobotState.HOMING_AND_TC, 'homing_completed', RobotState.ERASING_AND_TC)
        self.state_machine.add_transition(RobotState.ERASING_AND_TC, 'erasing_completed', RobotState.WAIT_FOR_RAPID)
        self.state_machine.add_transition(RobotState.WAIT_FOR_RAPID, 'rapid_idle', RobotState.IDLE)

        
        # Reset transition to idle state
        self.state_machine.add_transition(RobotState.IDLE, 'reset', RobotState.IDLE)
        self.state_machine.add_transition(RobotState.WAITING_FOR_INFERENCE, 'reset', RobotState.IDLE)
        self.state_machine.add_transition(RobotState.PROCESSING_INFERENCE, 'reset', RobotState.IDLE)
        self.state_machine.add_transition(RobotState.DRAWING_SIM, 'reset', RobotState.IDLE)

        # Error transitions from any state
        for state in RobotState:
            if state not in [RobotState.ERROR, RobotState.EMERGENCY_STOP]:
                self.state_machine.add_transition(state, 'error', RobotState.ERROR)
                self.state_machine.add_transition(state, 'emergency_stop', RobotState.EMERGENCY_STOP)
        
        # Recovery transitions
        self.state_machine.add_transition(RobotState.ERROR, 'reset', RobotState.IDLE)
        self.state_machine.add_transition(RobotState.EMERGENCY_STOP, 'reset', RobotState.IDLE)
        
        # Add state handlers
        self.state_machine.add_state_handler(RobotState.INIT, self.handle_init_state)
        self.state_machine.add_state_handler(RobotState.IDLE, self.handle_idle_state)
        self.state_machine.add_state_handler(RobotState.WAITING_FOR_INFERENCE, self.handle_waiting_for_inference_state)
        self.state_machine.add_state_handler(RobotState.PROCESSING_INFERENCE, self.handle_processing_inference_state)
        self.state_machine.add_state_handler(RobotState.SETTING_UP_ROBOT, self.setup_robot_state)
        self.state_machine.add_state_handler(RobotState.DRAWING_SIM, self.handle_drawing_state_sim)
    
        self.state_machine.add_state_handler(RobotState.DRAWING_REAL, self.handle_drawing_state_real)
        # self.state_machine.add_state_handler(RobotState.HOMING_AND_TC, self.handle_homing_and_tc_state)
        self.state_machine.add_state_handler(RobotState.ERASING_AND_TC, self.handle_erase_and_tc_state)
        self.state_machine.add_state_handler(RobotState.WAIT_FOR_RAPID, self.handle_wait_for_rapid)

        self.state_machine.add_state_handler(RobotState.ERROR, self.handle_error_state)
        self.state_machine.add_state_handler(RobotState.EMERGENCY_STOP, self.handle_emergency_stop_state)
        
        # Add entry handlers
        self.state_machine.add_entry_handler(RobotState.IDLE, self.on_enter_idle)
        self.state_machine.add_entry_handler(RobotState.WAITING_FOR_INFERENCE, self.on_enter_waiting_for_inference)
        self.state_machine.add_entry_handler(RobotState.ERROR, self.on_enter_error)
        self.state_machine.add_entry_handler(RobotState.EMERGENCY_STOP, self.on_enter_emergency_stop)

        self.state_machine.add_entry_handler(RobotState.DRAWING_REAL, self.on_enter_drawing_state_real)
        # self.state_machine.add_entry_handler(RobotState.HOMING_AND_TC, self.on_enter_homing_and_tc_state)
        self.state_machine.add_entry_handler(RobotState.ERASING_AND_TC, self.on_enter_erase_and_tc_state)
        self.state_machine.add_entry_handler(RobotState.WAIT_FOR_RAPID, self.on_enter_wait_for_rapid)

    # State machine callback
    def state_machine_callback(self):
        """Main state machine execution loop"""
        self.state_machine.execute()
        self.current_key = None  # Reset key after processing

    # State handlers
    def handle_init_state(self):
        """Handle initialization state"""
        # Perform any initialization tasks
        self.get_logger().info("Initializing the robot system...")
        
        if self.useRWS:
            self.get_logger().info("Checking connection to RWS")
            if not self.rws_client.is_logged_in():
                self.rws_client.login()
                if self.rws_client.is_logged_in():
                    self.get_logger().info("Successfully connected to RWS")
                    self.state_machine.trigger_event('initialized')
                    return
                else:
                    self.get_logger().error("Failed to connect to RWS, going to ERROR state")
                    self.state_machine.trigger_event('error')
                    return
        else:
            self.get_logger().info("Skipping RWS connection for debug purposes")
            # Simulate successful initialization
            self.state_machine.trigger_event('initialized')
            return

    ## Idle state

    def on_enter_idle(self):
        """Called when entering idle state"""
        self.current_inference_result = None  # Reset inference result
        self.points = []  # Reset points
        self.get_logger().info('Entering IDLE state')
        self.iter = 0  # Reset iteration counter
        self.rapid_ready = False


    def handle_idle_state(self):
        """Handle idle state - waiting for commands or starting inference"""

        if self.current_key == 's':
            self.get_logger().info('Starting inference process...')
            self.state_machine.trigger_event('start_inference')
            return

        # periodically check connectino to RWS
        if self.useRWS:

            checkRWS = self.iter % 50 == 0
            self.iter += 1
            if checkRWS:
                self.iter = 1
                if not self.rws_client.is_logged_in():
                    self.get_logger().warn("RWS connection lost, trying to reconnect...")
                    try:
                        self.rws_client.login()
                        if self.rws_client.is_logged_in():
                            self.get_logger().info("Reconnected to RWS")
                        else:
                            self.get_logger().error("Failed to reconnect to RWS, going to ERROR state")
                            self.state_machine.trigger_event('error')
                            return
                    except RWSException as e:
                        self.get_logger().error(f"RWS connection error: {e}")
                        self.state_machine.trigger_event('error')
                        return
                else:
                    self.get_logger().info("RWS connection is active and ready")


    ## Waiting for inference state                      
    
    def on_enter_waiting_for_inference(self):
        """Called when entering waiting for inference state"""
        self.get_logger().info('Entering WAITING_FOR_INFERENCE state - requesting inference')
        self.start_publisher.publish(std_msgs.String(data='start_inference'))
        if not self.useRWS:
            # Clear turtle simulator before starting new inference
            self.clear_turtle_publisher.publish(std_msgs.Bool(data=True))
            self.get_logger().info('Cleared turtle simulator for new inference')

    def handle_waiting_for_inference_state(self):
        """Handle waiting for inference result"""

        if self.current_key == 'r':
            self.get_logger().info('Resetting to idle state...')
            self.state_machine.trigger_event('reset')
            return

        self.iter += 1
        printBool = self.iter % 10 == 0

        if printBool:
            self.iter = 0
            self.get_logger().info('Waiting for inference result...')

        if self.state_machine.get_state_duration() > self.task_timeout:
            self.get_logger().warn('Inference timeout, goint to error')
            self.state_machine.trigger_event('error')
            return


    ## Processing inference state

    def handle_processing_inference_state(self):
        """Handle processing inference result"""

        if self.current_key == 'r':
            self.get_logger().info('Resetting to idle state...')
            self.state_machine.trigger_event('reset')
            return

        if self.current_inference_result:
             # Process the inference result and decide what to do
            self.get_logger().info(f'Processing inference result: {self.current_inference_result}')
            
            try:
                data = json.loads(self.current_inference_result)
                age = data.get('age')
                gender = data.get('gender')
                emotion = data.get('emotion')
            except Exception as e:
                self.get_logger().error(f"Failed to parse inference result: {e}")
                self.state_machine.trigger_event('error')
                return
    
            coord_string = (
                        f"Vek:       {age},\n"
                        f"Pohlavi:   {gender},\n"
                        f"Emoce:   {emotion}"
                        )
            self.points = path_generator.generate_path(coord_string, letter_height=60.0, letter_spacing=10, space_factor=1.3, line_spacing=1.5)

            
            if self.points:
                self.points.append((500.0, -350.0, 20.0))

                if self.generate_csv:
                    self.get_logger().info('Generating CSV file with points...')
                    with open("path.csv", "w") as f:
                        for (x, y, z) in self.points:
                            f.write(f"{x:.3f},{y:.3f},{z:.3f}\n")
                        print(f"CSV file generated with {len(self.points)} points.")
                self.iter = 0
                self.rapid_ready = False
                self.state_machine.trigger_event('setup_robot')
                return
            else:
                self.get_logger().error('Failed to generate path, going to error state')
                self.state_machine.trigger_event('error')
                return

    ## Setup robot state
    def setup_robot_state(self):
        """Handle task execution state"""
        if self.useRWS:
            #self.get_logger().info("Checking mastership privileges...")
            if not self.rws_wrappers.is_master("edit"):
                self.get_logger().info("Asking robot for mastership...")
                status = self.rws_wrappers.request_mastership("edit")
                if not status:
                    self.get_logger().error("Failed to get mastership, going to ERROR state")
                    self.state_machine.trigger_event('error')
                    return
            
            time.sleep(0.1)  # Wait for mastership to be granted
            #self.get_logger().info("Checking if RAPID script is already running...")
            if not self.rws_wrappers.is_running():
                self.get_logger().info("RAPID script is not running, starting it...")

                self.get_logger().info("Checking robot operation state...")
                resp = self.rws_wrappers.get_opmode_state()
                if not resp[0] == "auto":
                    self.get_logger().error(f"Robot is not in AUTO mode, current mode: {resp[0]}, change to AUTO mode on the robot controller")
                    self.state_machine.trigger_event('error')
                    return
                    
                resp = self.rws_wrappers.get_controller_state()
                if not resp[0] == "motoron":
                    self.get_logger().warn(f"Robot controller is not in MOTOR ON state, current state: {resp[0]}")
                    self.get_logger().info("Trying to turn motors on...")
                    status = self.rws_wrappers.motors_on()
                    if status:
                        self.get_logger().info("Motors turned on successfully")
                    else:
                        self.get_logger().error("Failed to turn motors on, going to ERROR state")
                        self.state_machine.trigger_event('error')
                        return
                
                self.get_logger().info("Resetting Program pointer...")
                status = self.rws_wrappers.reset_pp()
                if status:
                    self.get_logger().info("Program pointer reset successfully")
                self.get_logger().info("Starting RAPID script...")
                
                status = self.rws_wrappers.start_rapid_script()
                if status:
                    self.get_logger().info("RAPID script started successfully")
                    self.rapid_ready = True
            
            else:
                self.iter += 1
                if self.iter % 10 == 0:
                    self.get_logger().info("RAPID script is already running")
                    self.get_logger().info('Waiting for RAPID to enter idle state...')
                    self.iter = 0
                    state, _ = self.rws_wrappers.get_rapid_symbol_int("current_state", "TRobMain")

                    if state == 0:
                        self.get_logger().info('RAPID is in idle state')
                        self.rapid_ready = True
                    else:
                        self.get_logger().warn(f'RAPID is not in idle state, current state: {state}, waiting...')
            
            if self.rapid_ready:
                time.sleep(2)
                self.rws_wrappers.set_rapid_symbol_string("home_routine", "routine_name_input", "TRobRAPID")
                self.rws_wrappers.set_rapid_symbol_int(2, "current_state", "TRobMain")
                time.sleep(0.5)
                self.state_machine.trigger_event('start_drawing_real')
                return

        else:
            self.state_machine.trigger_event('start_movement_sim')
            return
        

    def on_enter_drawing_state_real(self): 
        """Called when entering drawing state for real robot"""
        self.get_logger().info('Entering DRAWING_REAL state')
        self.iter = 0
        self.rapid_ready = False

        # Initialize points for drawing
        if not self.points:
            self.get_logger().error('No points to draw, going to ERROR state')
            self.state_machine.trigger_event('error')
            return
        
        if not self.rws_wrappers.is_running():
            self.get_logger().error('RAPID is not running, going to ERROR state')
            self.state_machine.trigger_event('error')
            return

            
    ## Drawing state for real robot
    def handle_drawing_state_real(self):
        """Handle drawing state for real robot"""

        if self.rapid_ready:
            try:
                point = self.points[self.iter]
                X, Y, Z = point
                self.rws_wrappers.send_dipc_message(f'[[{X},{Y},{Z}],[0,1,0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]', 'robtarget')
                self.iter += 1
                if self.iter >= len(self.points):
                    self.get_logger().info('All points sent, waiting for movement to finish...')
                    self.state_machine.trigger_event('drawing_completed')
                    return
            except Exception as e:
                    self.get_logger().info(f"Error sending DIPC message: {e}")
                    time.sleep(0.4)
        else:
            self.iter += 1
            if self.iter % 10 == 0:
                self.get_logger().info('Waiting for RAPID to enter idle state...')
                self.iter = 0
                state, _ = self.rws_wrappers.get_rapid_symbol_int("current_state", "TRobMain")

                if state == 0:
                    self.get_logger().info('RAPID is in idle state, starting drawing task...')
                    time.sleep(0.5)
                    self.rws_wrappers.set_rapid_symbol_string("draw_routine_buffer", "routine_name_input", "TRobRAPID")
                    self.rws_wrappers.set_rapid_symbol_int(2, "current_state", "TRobMain")
                    time.sleep(0.5) # Give some time for RAPID to start the routine
                    self.rapid_ready = True
                else:
                    self.get_logger().warn(f'RAPID is not in idle state, current state: {state}, waiting...')

    # def on_enter_homing_and_tc_state(self):
    #     """Called when entering homing and tool change state"""
    #     self.get_logger().info('Entering HOMING_AND_TC state')
    #     self.iter = 0
    #     self.rapid_ready = False

    #     if not self.rws_wrappers.is_running():
    #         self.get_logger().error('RAPID is not running, going to ERROR state')
    #         self.state_machine.trigger_event('error')
    #         return


    # def handle_homing_and_tc_state(self):
        
    #         self.iter += 1
    #         if self.iter % 10 == 0:
    #             self.get_logger().info('Waiting for RAPID to enter idle state...')
    #             self.iter = 0
    #             state, _ = self.rws_wrappers.get_rapid_symbol_int("current_state", "TRobMain")

    #             if state == 0:
    #                 self.get_logger().info('RAPID is in idle state, starting drawing task...')
    #                 time.sleep(0.5)
    #                 self.rws_wrappers.set_rapid_symbol_string("home_routine", "routine_name_input", "TRobRAPID")
    #                 self.rws_wrappers.set_rapid_symbol_int(2, "current_state", "TRobMain")
    #                 time.sleep(0.5) # Give some time for RAPID to start the routine
    #                 self.state_machine.trigger_event('homing_completed')
    #                 return
    #             else:
    #                 self.get_logger().warn(f'RAPID is not in idle state, current state: {state}, waiting...')

    def on_enter_erase_and_tc_state(self):
        """Called when entering erase and tool change state"""
        self.get_logger().info('Entering ERASING_AND_TC state')
        self.iter = 0
        self.rapid_ready = False

        if not self.rws_wrappers.is_running():
            self.get_logger().error('RAPID is not running, going to ERROR state')
            self.state_machine.trigger_event('error')
            return


    def handle_erase_and_tc_state(self):

        if not self.rapid_ready:
            self.iter += 1
            if self.iter % 10 == 0:
                self.get_logger().info('Waiting for RAPID to enter idle state...')
                self.iter = 0
                state, _ = self.rws_wrappers.get_rapid_symbol_int("current_state", "TRobMain")

                if state == 0:
                    self.get_logger().info('RAPID is in idle state, press "e" to start erasing...')
                    self.rapid_ready = True
                else:
                    self.get_logger().warn(f'RAPID is not in idle state, current state: {state}, waiting...')
                    return
        else:
            if self.current_key == 'e':
                self.get_logger().info('Starting erasing task...')
                time.sleep(0.5)
                self.rws_wrappers.set_rapid_symbol_string("erase_routine", "routine_name_input", "TRobRAPID")
                self.rws_wrappers.set_rapid_symbol_int(2, "current_state", "TRobMain")
                time.sleep(0.5)
                self.state_machine.trigger_event('erasing_completed')
                return
    
    def on_enter_wait_for_rapid(self):
        """Called when entering wait for RAPID state"""
        self.get_logger().info('Entering WAIT_FOR_RAPID state')
        self.iter = 0
        self.rapid_ready = False

        # # Wait for RAPID to be ready
        if not self.rws_wrappers.is_running():
            self.get_logger().error('RAPID is not running, going to ERROR state')
            self.state_machine.trigger_event('error')
            return
            
        
    def handle_wait_for_rapid(self):
        
        if self.rapid_ready:
            self.get_logger().info('RAPID is ready, finishing task...')
            self.state_machine.trigger_event('rapid_idle')
        
        else:
            self.iter += 1
            if self.iter % 10 == 0:
                self.get_logger().info('Waiting for RAPID to enter idle state...')
                self.iter = 0
                state, _ = self.rws_wrappers.get_rapid_symbol_int("current_state", "TRobMain")

                if state == 0:
                    self.get_logger().info('RAPID is in idle state')
                    time.sleep(0.5)
                    self.rapid_ready = True
                else:
                    self.get_logger().warn(f'RAPID is not in idle state, current state: {state}, waiting...')



    def handle_drawing_state_sim(self):
        """Handle drawing state"""
            
        if not self.useRWS:
            if self.current_key == 'r':
                self.get_logger().info('Resetting to idle state...')
                self.clear_turtle_publisher.publish(std_msgs.Bool(data=True))
                self.state_machine.trigger_event('reset')

            # Simulate sending points to turtle simulator
            if self.iter < len(self.points):
                point = self.points[self.iter]

                if self.iter % 50 == 0:
                    self.get_logger().info(f'Sending point {self.iter + 1}/{len(self.points)}: {point}')
                msg = Point()
                msg.x, msg.y, msg.z = point
                self.point_publisher.publish(msg)
                self.iter += 1
            else:
                self.get_logger().info('All points sent, going back to IDLE state')
                self.state_machine.trigger_event('sim_task_completed')


    ## Error and emergency stop states
    def on_enter_error(self):
        """Called when entering error state"""
        self.get_logger().error('Entering ERROR state')

    def handle_error_state(self):
        """Handle error state"""
        # Could implement error recovery logic here
        if self.current_key == 'r':
            self.get_logger().info('Resetting from ERROR state...')
            self.state_machine.trigger_event('reset')



    def on_enter_emergency_stop(self):
        """Called when entering emergency stop state"""
        self.get_logger().error('EMERGENCY STOP activated!')

    def handle_emergency_stop_state(self):
        """Handle emergency stop state"""
        if self.current_key == 'r':
            self.get_logger().info('Resetting from ESTOP state...')
            self.state_machine.trigger_event('reset')



    # Callbacks for incoming messages

    def keypress_callback(self, msg):
        """Handle incoming keypress messages"""
        self.current_key = msg.data.lower()
        self.get_logger().info(f'Keypress callback: "{self.current_key}"')

        if self.current_key == 'q':
            self.get_logger().info('Emergency stop triggered from state: %s' % self.state_machine.current_state.name)
            self.state_machine.trigger_event('emergency_stop')

        
    def inference_callback(self, msg):
        """Handle incoming inference results"""
        self.get_logger().info('Received inference result: %s' % msg.data)
        
        if self.state_machine.current_state == RobotState.WAITING_FOR_INFERENCE:
            self.current_inference_result = msg.data
            self.state_machine.trigger_event('inference_received')
        else:
            self.get_logger().warn(f'Received inference while in {self.state_machine.current_state.name} state - ignoring')

    
    # Public methods for external control
    def trigger_emergency_stop(self):
        """Trigger emergency stop from external source"""
        self.state_machine.trigger_event('emergency_stop')

    def reset_from_error(self):
        """Reset from error state"""
        if self.state_machine.current_state in [RobotState.ERROR, RobotState.EMERGENCY_STOP]:
            self.state_machine.trigger_event('reset')

    def get_current_state(self) -> RobotState:
        """Get the current state"""
        return self.state_machine.current_state


def main(args=None):
    rclpy.init(args=args)

    master_node = MasterNode()
    try:
        rclpy.spin(master_node)
    except Exception as e:
        master_node.get_logger().error(f'Exception occurred: {e}')
    finally:
        master_node.rws_client.logout()
        master_node.get_logger().info('Shutting down Master Node...')
        master_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()