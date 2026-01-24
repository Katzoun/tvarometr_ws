import time
from enum import Enum, auto
from typing import Dict, Callable, Optional

class RobotState(Enum):
    """Define all possible states for the robot state machine"""
    INIT = auto()
    IDLE = auto()
    WAITING_FOR_INFERENCE = auto()
    PROCESSING_INFERENCE = auto()
    DRAWING_SIM = auto()
    SETTING_UP_ROBOT = auto()
    DRAWING_REAL = auto()
    HOMING_AND_TC = auto()
    ERASING_AND_TC = auto()
    WAIT_FOR_RAPID = auto()



    ERROR = auto()
    EMERGENCY_STOP = auto()


class StateMachine:
    """State machine implementation for robot control"""
    
    def __init__(self, initial_state: RobotState = RobotState.INIT):
        self.current_state = initial_state
        self.previous_state = None
        self.state_start_time = time.time()
        self.transitions: Dict[RobotState, Dict[str, RobotState]] = {}
        self.state_handlers: Dict[RobotState, Callable] = {}
        self.entry_handlers: Dict[RobotState, Callable] = {}
        self.exit_handlers: Dict[RobotState, Callable] = {}
        
    def add_transition(self, from_state: RobotState, event: str, to_state: RobotState):
        """Add a state transition"""
        if from_state not in self.transitions:
            self.transitions[from_state] = {}
        self.transitions[from_state][event] = to_state
    
    def add_state_handler(self, state: RobotState, handler: Callable):
        """Add a handler function for a state (called while in the state)"""
        self.state_handlers[state] = handler
    
    def add_entry_handler(self, state: RobotState, handler: Callable):
        """Add an entry handler (called when entering the state)"""
        self.entry_handlers[state] = handler
    
    def add_exit_handler(self, state: RobotState, handler: Callable):
        """Add an exit handler (called when leaving the state)"""
        self.exit_handlers[state] = handler
    
    def trigger_event(self, event: str) -> bool:
        """Trigger an event that may cause a state transition"""
        if self.current_state in self.transitions:
            if event in self.transitions[self.current_state]:
                new_state = self.transitions[self.current_state][event]
                return self.change_state(new_state)
        return False
    
    def change_state(self, new_state: RobotState) -> bool:
        """Change to a new state"""
        if new_state == self.current_state:
            return False
            
        # Call exit handler for current state
        if self.current_state in self.exit_handlers:
            self.exit_handlers[self.current_state]()
        
        self.previous_state = self.current_state
        self.current_state = new_state
        self.state_start_time = time.time()
        
        # Call entry handler for new state
        if new_state in self.entry_handlers:
            self.entry_handlers[new_state]()
            
        return True
    
    def execute(self):
        """Execute the current state handler"""
        if self.current_state in self.state_handlers:
            self.state_handlers[self.current_state]()
    
    def get_state_duration(self) -> float:
        """Get how long we've been in the current state"""
        return time.time() - self.state_start_time