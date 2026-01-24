# rws_wrappers.py
from .exceptions import RWSException
import utils.rwsutils as rwsutils

import json

class RWSWrappers:


    def __init__(self, client):
        """
        client: Instance of RWSClient that provides methods to interact with the RWS API.
        """
        self.client = client

    ###################################
    ## GET METHODS
    ###################################

    def get_clock(self):
        """ Returns the current clock value from the robot controller. """
        (data, status) = self.client.get_request("/ctrl/clock")
        data = data['state'][0]
        return (data.get('datetime', 'unknown'), status)
    
    def get_controller_state(self):
        """ Returns the state of the controller (motors on/off, guardstop, emergencystop, init) """
        (data, status) = self.client.get_request("/rw/panel/ctrl-state")
        data = data['state'][0]
        return (data.get('ctrlstate', 'unknown').lower(), status)

    def get_opmode_state(self):
        """ Returns the current operational mode of the robot (auto, man, manf) """
        (data, status) = self.client.get_request("/rw/panel/opmode")
        data = data['state'][0]
        return (data.get('opmode', 'unknown').lower(), status)

    def is_master(self, domain=None):
        """ 
        Returns True if the client has mastership on given domain (Edit or Motion), False otherwise 
        """
        if domain not in ['edit', 'motion']:
            raise RWSException("Invalid domain specified")
        
        if domain:
            (data,status) = self.client.get_request(f"/rw/mastership/{domain}")
            mastership  = data.get('state', [])[0]
            held_by_me = mastership.get('mastershipheldbyme', False)
            if held_by_me:
                return True
            else:
                return False
            
    def get_safety_mode(self):
        """ Returns the current safety mode of the robot """
        (data, status) = self.client.get_request("/ctrl/safety/mode")
        data = data['state'][0]
        #print(data)
        safety_mode = data.get('safetymode', 'unknown')
        return (safety_mode, status)
            
    def get_speedratio(self):
        """ Returns the current speed ratio of the robot """
        (data, status) = self.client.get_request("/rw/panel/speedratio")
        data = data['state'][0]
        speedratio_str = data.get('speedratio', '-1')
        speedratio = int(speedratio_str)
        return (speedratio, status)
    
    def get_network_info(self):
        """ Returns the network information of the robot (DOES NOT WORK ON VIRTUAL CONTROLLER) """
        (data, status) = self.client.get_request("/ctrl/network")
        data = data['state'][0]
        print(data)
        network_info = data.get('network', {})
        return (network_info, status)
    
    def get_robot_type(self):
        """ Returns the type of the robot (e.g., CRB 15000-10/1.52,) """
        (data, status) = self.client.get_request("/rw/system/robottype")
        data = data['state'][0]
        #print(data)
        robot_type = data.get('robot-type', 'unknown')

        return (robot_type, status)

    def get_system_options(self):
        """ Returns the system options of the robot """
        (data, status) = self.client.get_request("/rw/system/options")
        data = data['state'][0]
        #print(data)
        options = data.get('option', {})
        return (options, status)
    
    def get_system_products(self):
        """ Returns the system products of the robot """
        (data, status) = self.client.get_request("/rw/system/products")
        data = data['state'][0]
        #print(data)
        return (data, status)
    
    def get_energy_info(self):
        """ Returns the energy information of the robot """
        (data, status) = self.client.get_request("/rw/system/energy")
        #print(data)
        data = data['state']
        #print(data)
        return (data, status)
    
    def get_mechunits(self):
        """ Returns the mechanical unit information of the robot """
        (data, status) = self.client.get_request("/rw/motionsystem/mechunits")
        resources = data.get('_embedded', {}).get('resources', [])[0]
        #print(resources)
        title = resources.get('_title', 'unknown')
        mode = resources.get('mode', 'unknown')
        return ({'_title': title, 'mode': mode}, status)
    
    # def get_mechunit_info(self, mechunit_name):
    #     """ Returns the information of a specific mechanical unit """
    #     if not mechunit_name:
    #         raise RWSException("Mechanical unit name cannot be empty")
        
    #     (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}")
    #     print(data)
    #     resources = data.get('_embedded', {}).get('resources', [])[0]
    #     #print(resources)
    #     title = resources.get('_title', 'unknown')
    #     mode = resources.get('mode', 'unknown')
    #     return ({'_title': title, 'mode': mode}, status)

    def get_leadthrough_state(self, mechunit_name = "ROB_1"):
        """ Returns the leadthrough state of the robot """
        if not mechunit_name:
            raise RWSException("Mechanical unit name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}/lead-through")
        data = data['state'][0]
        #print(data)
        leadthrough_state = data.get('status', 'unknown')
        return (leadthrough_state, status)
    
    def get_robot_baseframe(self, mechunit_name = "ROB_1"):
        """ 
        Returns the robot base frame information in format [[x, y, z], [q1, q2, q3, q4]]
        """
        if not mechunit_name:
            raise RWSException("Mechanical unit name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}/baseframe")
        data = data['state'][0]
        baseframe = data.get('baseframe', {})
        # Extract and convert to float
        x = float(baseframe.get('x', 0))
        y = float(baseframe.get('y', 0))
        z = float(baseframe.get('z', 0))
        q1 = float(baseframe.get('q1', 0))
        q2 = float(baseframe.get('q2', 0))
        q3 = float(baseframe.get('q3', 0))
        q4 = float(baseframe.get('q4', 0))
        result = [[x, y, z], [q1, q2, q3, q4]]
        return (result, status)
    
    def get_robot_cartesian(self, mechunit_name = "ROB_1"):
        """ 
        Returns the robot cartesian position in format [[x, y, z], [q1, q2, q3, q4]]
        """
        if not mechunit_name:
            raise RWSException("Mechanical unit name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}/cartesian")
        data = data['state'][0]
        #print(data)
        # Extract and convert to float
        x = float(data.get('x', 0))
        y = float(data.get('y', 0))
        z = float(data.get('z', 0))
        q1 = float(data.get('q1', 0))
        q2 = float(data.get('q2', 0))
        q3 = float(data.get('q3', 0))
        q4 = float(data.get('q4', 0))
        result = [[x, y, z], [q1, q2, q3, q4]]
        return (result, status)
    
    def get_robot_robtarget(self, mechunit_name = "ROB_1"):
        """ 
        Returns the robot robtarget position in format [[x, y, z], [q1, q2, q3, q4]]
        """
        if not mechunit_name:
            raise RWSException("Mechanical unit name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}/robtarget")
        data = data['state'][0]
        #print(data)
        # Extract and convert to float
        x = float(data.get('x', 0))
        y = float(data.get('y', 0))
        z = float(data.get('z', 0))
        q1 = float(data.get('q1', 0))
        q2 = float(data.get('q2', 0))
        q3 = float(data.get('q3', 0))
        q4 = float(data.get('q4', 0))
        result = [[x, y, z], [q1, q2, q3, q4]]
        return (result, status)
    
    def get_robot_jointtarget(self, mechunit_name = "ROB_1"):
        """ 
        Returns the robot joint target position in format [j1, j2, j3, j4, j5, j6]
        """
        if not mechunit_name:
            raise RWSException("Mechanical unit name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/motionsystem/mechunits/{mechunit_name}/jointtarget")
        data = data['state'][0]
        #print(data)
        # Extract and convert to float
        joints = [float(data.get(f'rax_{i+1}', -999)) for i in range(6)]
        return (joints, status)
         
    
    def get_io_networks(self): 
        """ Returns the IO networks of the robot """
        (data, status) = self.client.get_request("/rw/iosystem/networks")
        resources = data.get('_embedded', {}).get('resources', [])
        networks = [res.get('_title') for res in resources if res.get('_title')]
        #print(networks)
        return (networks, status)
    
    def get_io_signals(self):
        """ Returns the IO signals of the robot """
        (data, status) = self.client.get_request("/rw/iosystem/signals")
        resources = data.get('_embedded', {}).get('resources', [])
        signals = [res.get('_title') for res in resources if res.get('_title')]
        #print(signals)
        return (signals, status)
    
    def get_io_signal(self, signal_name, network="", device=""):
        """ 
        Returns the IO signal state for a specific signal. 
        For some signals, network and device does not have to be specified.
        """
        if not signal_name:
            raise RWSException("Signal name cannot be empty")
        if network:
            network = network if network.endswith('/') else network + '/'
        if device:
            device = device if device.endswith('/') else device + '/'

        path = f"/rw/iosystem/signals/{network}{device}{signal_name}"

        (data, status) = self.client.get_request(path)
        resource = data.get('_embedded', {}).get('resources', [])
        #print(resource)
        result = {'lvalue': resource[0].get('lvalue'),'type': resource[0].get('type')}

        return (result, status)
    
    def get_rapid_execution_state(self):
        """ Returns the current state of the RAPID execution """
        (data, status) = self.client.get_request("/rw/rapid/execution")
        data = data['state'][0]

        result = {'ctrlexecstate' : data.get('ctrlexecstate'), 'cycle' : data.get('cycle')}
        return (result, status)
    
    def is_running(self):
        """ Returns True if the RAPID execution is running, False otherwise """
        (data, status) = self.get_rapid_execution_state()
        if status != 200:
            raise RWSException("Failed to get RAPID execution state")
        #print(data)
        # Check if the execution state is 'running' or "stopped'

        if data.get('ctrlexecstate', 'unknown').lower() == 'running':
            return True
        elif data.get('ctrlexecstate', 'unknown').lower() == 'stopped':
            return False
        else:
            raise RWSException(f"Unknown RAPID execution state: {data.get('ctrlexecstate', 'unknown')}")
    
    
    # def get_rapid_symbols(self):
    #     """ Returns the list of RAPID symbols """
    #     (data, status) = self.client.get_request("/rw/rapid/symbols")
    #     print(data)
    #     resources = data.get('_embedded', {}).get('resources', [])
    #     symbols = [res.get('_title') for res in resources if res.get('_title')]
    #     return (symbols, status)
    
    def get_rapid_tasks(self, ActiveOnly=False):
        """ Returns the list of RAPID tasks """
        (data, status) = self.client.get_request("/rw/rapid/tasks")
        #print(data)
        resources = data.get('_embedded', {}).get('resources', [])
        tasks = [res.get('_title') for res in resources if res.get('_title') and (not ActiveOnly or res.get('active', False))]
        return (tasks, status)
    
    # def get_task_motion(self, task_name):
    #     """ 
    #     Returns the motion information of a specific RAPID task.
    #     task_name: Name of the RAPID task.
    #     """
    #     if not task_name:
    #         raise RWSException("Task name cannot be empty")

    #     (data, status) = self.client.get_request(f"/rw/rapid/tasks/{task_name}/motion")
    #     print(data)
    #     data = data['state'][0]
    #     #print(data)
    #     joints = [float(data.get(f'rax_{i+1}', -999)) for i in range(6)]
    #     return (joints, status)

    def get_task_robtarget(self, task_name = "T_ROB1"):
        """ 
        Returns the robtarget information of a specific RAPID task.
        task_name: Name of the RAPID task.
        """
        if not task_name:
            raise RWSException("Task name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/rapid/tasks/{task_name}/motion/robtarget")
        #print(data)
        data = data['state'][0]
        #print(data)
        x = float(data.get('x', 0))
        y = float(data.get('y', 0))
        z = float(data.get('z', 0))
        q1 = float(data.get('q1', 0))
        q2 = float(data.get('q2', 0))
        q3 = float(data.get('q3', 0))
        q4 = float(data.get('q4', 0))
        result = [[x, y, z], [q1, q2, q3, q4]]
        return (result, status)
    
    
    def get_task_jointtarget(self, task_name = "T_ROB1"):
        """ 
        Returns the jointtarget information of a specific RAPID task.
        task_name: Name of the RAPID task.
        """
        if not task_name:
            raise RWSException("Task name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/rapid/tasks/{task_name}/motion/jointtarget")
        #print(data)
        data = data['state'][0]
        #print(data)
        joints = [float(data.get(f'rax_{i+1}', -999)) for i in range(6)]
        return (joints, status)
    
    def get_task_modules(self, task_name = "T_ROB1"):
        """ 
        Returns the list of modules in a specific RAPID task.
        task_name: Name of the RAPID task.
        """
        if not task_name:
            raise RWSException("Task name cannot be empty")

        (data, status) = self.client.get_request(f"/rw/rapid/tasks/{task_name}/modules")
        #print(data)
        data = data['state']
        modules = [res.get('_title') for res in data if res.get('_title')]
        return (modules, status)
    
    def get_rapid_symbol_raw(self, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the value of a specific RAPID symbol.
        """
        if not symbol_name or not module_name:
            raise RWSException("Symbol name and module name cannot be empty")
        
        symbol_url = f"RAPID%2F{task_name}%2F{module_name}%2F{symbol_name}"

        (data, status) = self.client.get_request(f"/rw/rapid/symbol/{symbol_url}/data")
        #print(data)
        data = data['state'][0]
        #print(data)
        value = data.get('value', 'unknown')
        return (value, status)
    
    def get_rapid_symbol_int(self, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the integer value of a specific RAPID symbol.
        """
        (value, status) = self.get_rapid_symbol_raw(symbol_name, module_name, task_name)
        try:
            value = int(value)
        except ValueError:
            raise RWSException(f"Symbol {symbol_name} in module {module_name} is not an integer")
        
        return (value, status)
    
    def get_rapid_symbol_string(self, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the string value of a specific RAPID symbol.
        """
        (value, status) = self.get_rapid_symbol_raw(symbol_name, module_name, task_name)
        if not isinstance(value, str):
            raise RWSException(f"Symbol {symbol_name} in module {module_name} is not a string")
        
        return (value, status)
    
    def get_rapid_symbol_bool(self, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the boolean value of a specific RAPID symbol.
        """
        (value, status) = self.get_rapid_symbol_raw(symbol_name, module_name, task_name)
        if isinstance(value, str):
            value = value.lower() in ['true', '1']
        elif isinstance(value, bool):
            value = bool(value)
        else:      
            raise RWSException(f"Symbol {symbol_name} in module {module_name} is not a boolean")
        return (value, status)
    
    def get_rapid_symbol_float(self, symbol_name, module_name, task_name="T_ROB1"):
        "Returns the float value of a specific RAPID symbol."
    
        (value, status) = self.get_rapid_symbol_raw(symbol_name, module_name, task_name)
        try:
            value = float(value)
        except ValueError:
            raise RWSException(f"Symbol {symbol_name} in module {module_name} is not a float")
        
        return (value, status)
    
    def get_rapid_symbol_properties(self, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the properties of a specific RAPID symbol.
        """
        if not symbol_name or not module_name:
            raise RWSException("Symbol name and module name cannot be empty")
        symbol_url = f"RAPID%2F{task_name}%2F{module_name}%2F{symbol_name}"

        (data, status) = self.client.get_request(f"/rw/rapid/symbol/{symbol_url}/properties")
        data = data.get('_embedded', {}).get('resources', [])[0]
        #print(data)
        properties = {
            'datatype': data.get('dattyp', 'unknown'),
            'local': data.get('local', 'unknown'),
            'symboltype': data.get('symtyp', 'unknown')
        }
        return (properties, status)
    
    def get_rapid_tool(self, tool_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the tooldata of specific tool.
        tool_name: Name of the tool.
        module_name: Name of the module.
        task_name: Name of the RAPID task.
        """
        if not tool_name or not module_name:
            raise RWSException("Tool name and module name cannot be empty")
        (data, status) = self.get_rapid_symbol_raw(tool_name, module_name, task_name)
        #print(data)
        tooldata = rwsutils.string_to_list(data)

        return (tooldata, status)
    
    def get_rapid_wobj(self, wobj_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the wobjdata of specific tool.
        wobj_name: Name of the workobject.
        module_name: Name of the module.
        task_name: Name of the RAPID task.
        """
        if not wobj_name or not module_name:
            raise RWSException("Tool name and module name cannot be empty")
        (data, status) = self.get_rapid_symbol_raw(wobj_name, module_name, task_name)
        #print(data)
        wobjdata = rwsutils.string_to_list(data)

        return (wobjdata, status)
    
    def get_rapid_robtarget(self, robtarget_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the robtarget data of specific robtarget.
        robtarget_name: Name of the robtarget.
        module_name: Name of the module.
        task_name: Name of the RAPID task.
        """
        if not robtarget_name or not module_name:
            raise RWSException("Tool name and module name cannot be empty")
        
        (data, status) = self.get_rapid_symbol_raw(robtarget_name, module_name, task_name)
        #print(data)
        robtarget = rwsutils.string_to_list(data)

        return (robtarget, status)
    
    def get_rapid_jointtarget(self, jointtarget_name, module_name, task_name="T_ROB1"):
        """ 
        Returns the jointtarget data of specific jointtarget.
        jointtarget_name: Name of the jointtarget.
        module_name: Name of the module.
        task_name: Name of the RAPID task.
        """
        if not jointtarget_name or not module_name:
            raise RWSException("Tool name and module name cannot be empty")
        
        (data, status) = self.get_rapid_symbol_raw(jointtarget_name, module_name, task_name)
        #print(data)
        jointtarget = rwsutils.string_to_list(data)

        return (jointtarget, status)
    
    def get_dipc_queues(self):
        """ 
        Returns the information about the DIPC queues.
        """
        (data, status) = self.client.get_request("/rw/dipc")
        if status != 200:
            raise RWSException("Failed to get DIPC information")
        
        #print(data)
        resources = data.get('_embedded', {}).get('resources', [])
        queues = []
        for res in resources:
            queues.append(res.get('_title'))
        
        return (queues, status)
    
    def get_dipc_queue_info(self, queue_name="RMQ_T_ROB1"):
        """ 
        Returns the information about a specific DIPC queue.
        queue_name: Name of the DIPC queue.
        """
        if not queue_name:
            raise RWSException("Queue name cannot be empty")
        
        (data, status) = self.client.get_request(f"/rw/dipc/{queue_name}/information")
        if status != 200:
            raise RWSException(f"Failed to get DIPC queue {queue_name} information")
        data = data.get('_embedded', {}).get('resources', [])[0]
        #print(data)
        return (data, status)
    
    
    def read_dipc_message(self, queue_name="RMQ_T_ROB1", timeout=0):
        """ 
        Reads a message from the specified DIPC queue.
        queue_name: Name of the DIPC queue.
        timeout: Timeout in seconds (default is 0, which means no timeout).
        """

        if not queue_name:
            raise RWSException("Queue name cannot be empty")
        if not isinstance(timeout, int) or timeout < 0:
            raise RWSException("Timeout must be a non-negative integer")
        
        params = {'timeout': str(timeout)} if timeout > 0 else {}
        (data, status) = self.client.get_request(f"/rw/dipc/{queue_name}?timeout={timeout}")
        
        if status != 200:
            raise RWSException(f"Failed to read message from DIPC queue {queue_name}")
        
        return (data, status)
    




    ##################################
    ## POST METHODS
    ##################################


    def motors_on(self):
        """ Turn on the motors """
        status = self.client.post_request("/rw/panel/ctrl-state", dataIn={'ctrl-state': 'motoron'})
        if status == 204:
            return True
        else:
            raise RWSException("Failed to turn on motors")

    def motors_off(self):
        """ Turn off the motors """
        status = self.client.post_request("/rw/panel/ctrl-state", dataIn={'ctrl-state': 'motoroff'})
        if status == 204:
            return True
        else:
            raise RWSException("Failed to turn off motors")
        
    def restart_controller(self):
        """ Restarts the controller, requires mastership on all domains. """
        
        if not (self.is_master('edit') and self.is_master('motion')):
            raise RWSException("Mastership on both edit and motion domains is required to restart the controller")

        status = self.client.post_request("/rw/panel/restart", dataIn={'restart-mode': 'restart'})
        if status == 204:
            return True
        else:
            raise RWSException("Failed to restart controller")

    def reset_pp(self):
        """ Resets the program pointer (PP) (mastership on edit domain is required) """
        if not self.is_master('edit'):
            raise RWSException("Mastership on edit domain is required to reset program pointer")
        
        status = self.client.post_request("/rw/rapid/execution/resetpp")
        if status == 204:
            return True
        else:
            raise RWSException("Failed to reset program pointer")

    def start_rapid_script(self):
        """ Starts the rapid script (mastership ONLY on edit domain is required. Mastership on motion domain will result in error) """
        
        if not self.is_master('edit') or self.is_master('motion'):
            raise RWSException("Mastership on edit domain is required to start rapid script. Mastership on motion domain will result in error")

        status = self.client.post_request("/rw/rapid/execution/start", dataIn={'regain' :'clear' ,'execmode' :'continue' ,'cycle' : 'once' ,'condition' : 'callchain' ,'stopatbp' : 'disabled','alltaskbytsp' : 'false'})
        if status == 204:
            return True
        else:
            raise RWSException("Failed to start rapid script")
        
    def stop_rapid_script(self):
        """ Stops the rapid script """
        status = self.client.post_request("/rw/rapid/execution/stop", dataIn={'stopmode' : 'stop', 'usetsp' : 'normal'})
        if status == 204:
            return True
        else:
            raise RWSException("Failed to stop rapid script")
        
    
    def request_mastership(self, domain=None):
        """ 
        Requests explicit mastership on selected domain ("edit" or "motion"). None = all domains.
        """
        if domain not in [None, 'edit', 'motion']:
            raise RWSException("Invalid domain specified")
        
        if domain:
            self.client.post_request(f"/rw/mastership/{domain}/request")
        else:
            self.client.post_request("/rw/mastership/request")

        # Check if mastership was granted
        if domain is None:
            if self.is_master('edit') and self.is_master('motion'):
                return True
            return False
        else:
            return self.is_master(domain)
        
    def release_mastership(self, domain=None):
        """ Releases mastership on given domain (Edit or Motion), 
        returns True if mastership was released, False otherwise. """
        
        if domain not in [None, 'edit', 'motion']:
            raise RWSException("Invalid domain specified")

        if domain:
            self.client.post_request(f"/rw/mastership/{domain}/release")
        else:
            self.client.post_request("/rw/mastership/release")
        
        if domain is None:
            if not (self.is_master('edit') or self.is_master('motion')):
                return True
            return False
        else:
            return not self.is_master(domain)
        
    def  set_io_signal(self,signal_name, signal_value, network="", device=""):
        """ 
        Sets the IO signal state for a specific signal.
        For some signals, network and device does not have to be specified.
        Returns True if the signal was set successfully
        """
        if not signal_name or signal_value is None:
            raise RWSException("Signal name or value cannot be empty")
        if network:
            network = network if network.endswith('/') else network + '/'
        if device:
            device = device if device.endswith('/') else device + '/'

        if isinstance(signal_value, bool):
            signal_value_str = '1' if signal_value else '0'
        elif isinstance(signal_value, int):
            signal_value_str = str(signal_value)

        path = f"/rw/iosystem/signals/{network}{device}{signal_name}/set-value"
        
        status = self.client.post_request(path, dataIn={'lvalue': signal_value_str})
        
        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to set IO signal {signal_name}")
        
    def set_jog_mechunit(self, mechunit_name="ROB_1"):
        """ 
        Sets the jog mode for a specific mechanical unit.
        mechunit_name: Name of the mechanical unit (e.g., "ROB_1").
        """

        path = f"/rw/motionsystem/{mechunit_name}"
        
        status = self.client.post_request(path)
        
        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to set jog mode for mechanical unit {mechunit_name}")
        
    # NOT WORKING
    # def jog_robot(self, axes_jog, ccount, inc_mode):
    #     """ 
    #     axes_pos: List of joint positions to jog the robot.
    #     ccount: Number of cycles to jog.
    #     inc_mode: 
    #     """
    #     if not mechunit_name:
    #         raise RWSException("Mechanical unit name cannot be empty")
        
    #     if not (0 <= speed <= 100):
    #         raise RWSException("Speed must be between 0 and 100")

    #     path = f"/rw/motionsystem/{mechunit_name}/jog"
        
    #     status = self.client.post_request(path, dataIn={'speed': speed})
        
    #     if status == 204:
    #         return True
    #     else:
    #         raise RWSException(f"Failed to jog robot in mechanical unit {mechunit_name}")
   
        
    # NOT WORKING

    # def set_opmode_state(self, mode):
    #     """ Sets the operational mode of the robot ("auto", "man") """
    #     """ does not work -- problem Operation rejected by the controller safety access restriction """

    #     if mode not in ['auto', 'man']:
    #         raise RWSException("Invalid operational mode specified")   
         

    #     status = self.client.post_request("/rw/panel/opmode/acknowledge", dataIn={'opmode': mode})
    #     print(status)
    #     self.client.post_request("/rw/panel/opmode", dataIn={'opmode': mode})

    #     # Check if the mode was set correctly
    #     current_mode = self.get_opmode_state()
    #     if current_mode == mode:
    #         return True
    #     else:
    #         raise RWSException(f"Failed to set operational mode to {mode}")
    
    # NOT WORKING
    # def set_safety_mode(self, mode):
    #     """ Sets the safety mode of the robot: "active", "commissioning", "service" """
        

    #     if mode not in ["active", "commissioning", "service"]:
    #         raise RWSException("Invalid safety mode specified")
        
    #     status = self.client.post_request("/ctrl/safety/mode", dataIn={'mode': mode})
        
    #     if status == 204:
    #         return True
    #     else:
    #         raise RWSException(f"Failed to set safety mode to {mode}")

    # def set_position_target(self, robtarget):
    #     """ 
    #     Sets the position target of the robot.
    #     robtarget: List in format [[x, y, z], [q1, q2, q3, q4], [c1, c2, c3, c4], [e1 ,e2, e3, e4, e5, e6]]
    #     """

    #     dataStr = (
    #         f"pos-x={str(robtarget[0][0])}"
    #         f"&pos-y={str(robtarget[0][1])}"
    #         f"&pos-z={str(robtarget[0][2])}"
    #         f"&orient-q1={str(robtarget[1][0])}"
    #         f"&orient-q2={str(robtarget[1][1])}"
    #         f"&orient-q3={str(robtarget[1][2])}"
    #         f"&orient-q4={str(robtarget[1][3])}"
    #         f"&config-j1={str(robtarget[2][0])}"
    #         f"&config-j4={str(robtarget[2][1])}"
    #         f"&config-j6={str(robtarget[2][2])}"
    #         f"&config-jx={str(robtarget[2][3])}"
    #         f"&extjoint-1={str(robtarget[3][0])}"
    #         f"&extjoint-2={str(robtarget[3][1])}"
    #         f"&extjoint-3={str(robtarget[3][2])}"
    #         f"&extjoint-4={str(robtarget[3][3])}"
    #         f"&extjoint-5={str(robtarget[3][4])}"
    #         f"&extjoint-6={str(robtarget[3][5])}"
    #     )
    #     status = self.client.post_request("/rw/motionsystem/position-target", dataIn=dataStr)

    #     if status == 204:
    #         return True
    #     else:
    #         raise RWSException("Failed to set position target")

    def set_speedratio(self, speed_ratio):
        """ Sets the speed ratio of the robot (0-100) """
        speed_ratio = int(speed_ratio)
        if not (0 <= speed_ratio <= 100):
            raise RWSException("Speed ratio must be between 0 and 100")

        status = self.client.post_request("/rw/panel/speedratio", dataIn={'speed-ratio': str(speed_ratio)})
        
        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to set speed ratio to {speed_ratio}")
        
    def reset_energy_info(self):
        """ Resets the accumulated energy information of the robot """
        status = self.client.post_request("/rw/system/energy/reset")
        
        if status == 204:
            return True
        else:
            raise RWSException("Failed to reset energy information")
        
    def set_rapid_symbol_raw(self, value, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Sets the value of a specific RAPID symbol
        Value has to be in string format.
        Requires mastership on edit domain.
        """
        if not symbol_name or not module_name:
            raise RWSException("Symbol name and module name cannot be empty")
        
        symbol_url = f"RAPID%2F{task_name}%2F{module_name}%2F{symbol_name}"

        status = self.client.post_request(f"/rw/rapid/symbol/{symbol_url}/data", dataIn={'value': value})
        
        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to set RAPID symbol {symbol_name} in module {module_name}")
    
    def set_rapid_symbol_int(self, value, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Sets the integer value of a specific RAPID symbol.
        Requires mastership on edit domain.
        """

        if not isinstance(value, int):
            try:
                value = int(value)
            except ValueError:
                raise RWSException("Value cannot be converted to an integer")
        
        status = self.set_rapid_symbol_raw(str(value), symbol_name, module_name, task_name)
        return status
    
    def set_rapid_symbol_string(self, value, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Sets the string value of a specific RAPID symbol.
        Requires mastership on edit domain.
        """
        if not isinstance(value, str):
            raise RWSException("Value must be a string")
        value_quoted = f'"{value}"'  # RAPID strings are quoted

        status = self.set_rapid_symbol_raw(value_quoted, symbol_name, module_name, task_name)
        return status
    
    def set_rapid_symbol_float(self, value, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Sets the float value of a specific RAPID symbol.
        Requires mastership on edit domain.
        """
        if not isinstance(value, float):
            try:
                value = float(value)
            except ValueError:
                raise RWSException("Value cannot be converted to a float")
        
        status = self.set_rapid_symbol_raw(str(value), symbol_name, module_name, task_name)
        return status
    
    def set_rapid_symbol_list(self, value, symbol_name, module_name, task_name="T_ROB1"):
        """ 
        Requires mastership on edit domain.
        """
        value_str = rwsutils.list_to_string(value)
        status = self.set_rapid_symbol_raw(value_str, symbol_name, module_name, task_name)
        return status
    
    def create_dipc_queue(self, queue_name, queue_size=100, message_size=100):
        """ 
        Creates an DIPC queue with the specified name and size.
        """
        if not queue_name:
            raise RWSException("Queue name cannot be empty")
        datastr = f'dipc-queue-name={queue_name}&dipc-queue-size={queue_size}&dipc-max-msg-size={message_size}'
        print(datastr)
        
        status = self.client.post_request("/rw/dipc", dataIn=datastr)
        
        if status == 201:
            return True
        else:
            raise RWSException(f"Failed to create IPC queue {queue_name}")

    def send_dipc_message_raw(self,raw_message, userdef = 1, queue_name = "RMQ_T_ROB1"):
        """ 
        Sends a message to the specified DIPC queue.
        """
        if not queue_name or not raw_message:
            raise RWSException("Queue name and message cannot be empty")
            
        payload={"dipc-src-queue-name": queue_name, "dipc-cmd": 0, "dipc-userdef": userdef,
                 "dipc-msgtype": 1, "dipc-data": raw_message}

        # message_str = f"dipc-src-queue-name={queue_name}&dipc-cmd=111&dipc-userdef=222&dipc-msgtype=1&dipc-data={message}"
        
        status = self.client.dipc_post_request(f"/rw/dipc/{queue_name}/?action=dipc-send", dataIn=payload)

        
        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to send message to IPC queue {queue_name}, queue is propably full")
        

    def send_dipc_message(self,message,rapid_dtype : str , userdef = 1, queue_name = "RMQ_T_ROB1"):
        """ 
        Sends a message to the specified DIPC queue.
        """
        if not queue_name or not message:
            raise RWSException("Queue name and message cannot be empty")
        msg_str = rapid_dtype + ";" + message
        #print(msg_str)
            
        payload={"dipc-src-queue-name": queue_name, "dipc-cmd": 0, "dipc-userdef": userdef,
                 "dipc-msgtype": 1, "dipc-data": msg_str}

        # message_str = f"dipc-src-queue-name={queue_name}&dipc-cmd=111&dipc-userdef=222&dipc-msgtype=1&dipc-data={message}"
        
        status = self.client.dipc_post_request(f"/rw/dipc/{queue_name}/?action=dipc-send", dataIn=payload)

        if status == 204:
            return True
        else:
            raise RWSException(f"Failed to send message to IPC queue {queue_name}, queue is propably full")

    #test run moveJ
    #get_request(conn, "/rw/rapid/symbol/RAPID%2FT_ROB1%2FTRobRAPID%2Fmove_robtarget_input/data")


#     robtarget_value = [
#     [1200, 0, 500],
#     [0, 0, -1, 0],
#     [0, -1, 0, 0],
#     [9E+9, 9E+9, 9E+9, 9E+9, 9E+9, 9E+9]
# ]
#     robtarget_value_str = json.dumps(robtarget_value)
#     post_request(conn, "/rw/rapid/symbol/RAPID%2FT_ROB1%2FTRobRAPID%2Fmove_robtarget_input/data?mastership=implicit" ,
#                dataIn={'value' : robtarget_value_str})


    #post_request(conn, "/rw/rapid/symbol/RAPID%2FT_ROB1%2FTRobRAPID%2Fmove_robtarget_input/data?mastership=implicit" ,
               #dataIn={'value' : '[[800,0,500],[0,0,-1,0],[0,-1,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]'})

    # post_request(conn, "/rw/rapid/symbol/RAPID%2FT_ROB1%2FTRobRAPID%2Froutine_name_input/data?mastership=implicit" ,
    #             dataIn={'value' : '"runMoveJ"'})