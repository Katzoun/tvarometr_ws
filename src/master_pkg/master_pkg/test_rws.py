import time
from  utils.rwsprovider import RWSClient
from utils.rwswrappers import RWSWrappers
import utils.rwsutils as rwsutils
import numpy as np

robotIP = "192.168.1.175"
username = "Admin"
password = "robotics"

if __name__ == "__main__":
    
    try:
        
        rwsCl = RWSClient(robotIP, username, password)
        rwsWrap  = RWSWrappers(rwsCl)

        rwsCl.login()

        print("Logged in:", rwsCl.is_logged_in())
        # # Example of getting the clock
        # clock = rwsWrap.get_clock()
        # print("Clock:", clock)

       
        # # print("Mastership edit:", rwsWrap.is_master("edit"))
        # # # #rwsWrap.stop_rapid_script()
        # print(rwsWrap.release_mastership("edit"))
        # time.sleep(1)
        print("Requesting mastership edit:", rwsWrap.request_mastership("edit"))
        print("Mastership edit:", rwsWrap.is_master("edit"))
        # rwsWrap.motors_on()
        # rwsWrap.reset_pp()
        # # time.sleep(1)
        # rwsWrap.start_rapid_script()
        print(rwsWrap.set_rapid_symbol_string("tool_tuzka", "tool_name", "TRobUser"))
        # print(rwsWrap.set_rapid_symbol_string("tool_tuzka", "tool_name", "TRobUser"))
        # time.sleep(1)
        print(rwsWrap.set_rapid_symbol_string("change_tool_new", "routine_name_input", "TRobRAPID"))
        print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))
        # time.sleep(6)
        # print(rwsWrap.set_rapid_symbol_string("smaz_tabuli", "routine_name_input", "TRobRAPID"))
        # print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))

        # print(rwsWrap.get_task_modules())
        # print("Mastership mot:", rwsWrap.is_master("motion"))
        # print(rwsWrap.release_mastership("edit"))
        #print(rwsWrap.create_dipc_queue("T_ROB1"))
        # print(rwsWrap.get_dipc_queues())
        # print(rwsWrap.get_dipc_queue_info())
        # print(rwsWrap.send_dipc_message('num;22'))
        # print(rwsWrap.start_rapid_script())

        time.sleep(6)

        #read points from csv file line by line
        with open('path.csv', 'r') as f:
            points = f.readlines()
        points = [line.strip().split(',') for line in points]
        points = [[float(coord) for coord in point] for point in points]
        # print(points)
        i =0 

        # s = np.linspace(0, 2*np.pi, 100)
        # X = 700 + 300 * np.sin(s)
        # Y = 700 +300 * np.cos(s) 
        # i=0

        # print(rwsWrap.read_dipc_message(timeout=5))
        # print("cc")

        print(rwsWrap.set_rapid_symbol_string("draw_routine_buffer", "routine_name_input", "TRobRAPID"))
        print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))


        # print(rwsWrap.set_rapid_symbol_string("runMoveJ", "routine_name_input", "TRobRAPID"))
        # print(rwsWrap.set_rapid_symbol_list([[500,500,0],[1,0,0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]], "move_robtarget_input", "TRobRAPID"))
        # print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))
        # # # print(rwsWrap.send_dipc_message('string;"cccc"'))
        # # # print(rwsWrap.send_dipc_message('string;"ahoj"'))
        # # # print(rwsWrap.send_dipc_message('string;"runMoveJ"'))
        time.sleep(2)

        # initialPos = [[1000, 0, 700], [0, 0, -1.0, 0], [0, 0, 0, 0], [9E+9, 9E+9, 9E+9, 9E+9, 9E+9, 9E+9]]

        while True:
            try:
                if i < len(points):

                    x,y,z = points[i]
                    status = rwsWrap.send_dipc_message(f'[[{x},{y},{-z}],[0,1,0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]', 'robtarget')
                    if status is True:
                        i += 1

                else:
                    break
                # if initialPos[0][0] > -1200:
                #     initialPos[0][0] -= 100
                # else:
                #     initialPos[0][0] = 1200



            except Exception as e:
                print(f"Error sending message: {e}")
                time.sleep(0.4)
                continue
            time.sleep(0.1)

        time.sleep(1)
        status = rwsWrap.send_dipc_message(f'[[{0},{-200},{200}],[0,1,0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]', 'robtarget')
        time.sleep(5)
        print(rwsWrap.set_rapid_symbol_raw(False, "run_buffer", "TRobUser"))
        
        time.sleep(15)

        print(rwsWrap.set_rapid_symbol_string("tool_houba", "tool_name", "TRobUser"))
        # print(rwsWrap.set_rapid_symbol_string("tool_tuzka", "tool_name", "TRobUser"))
        # time.sleep(1)
        print(rwsWrap.set_rapid_symbol_string("change_tool_new", "routine_name_input", "TRobRAPID"))
        print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))

        time.sleep(6)
        print(rwsWrap.set_rapid_symbol_string("smaz_tabuli", "routine_name_input", "TRobRAPID"))
        print(rwsWrap.set_rapid_symbol_int(2, "current_state", "TRobMain"))

        # print(rwsWrap.send_dipc_message('robtarget;[[1200,0,700],[0,0,-1.0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]'))
        # print(rwsWrap.send_dipc_message('robtarget;[[800,0,700],[0,0,-1.0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]'))
        # print(rwsWrap.send_dipc_message('robtarget;[[1000,500,700],[0,0,-1.0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]'))
        # print(rwsWrap.send_dipc_message('robtarget;[[-600,0,800],[0,0,-1.0,0],[0,0,0,0],[9E+9,9E+9,9E+9,9E+9,9E+9,9E+9]]'))

        # # print(rwsWrap.read_dipc_message(timeout=5))
        # print(rwsWrap.read_dipc_message(timeout=5))
        #(rwsWrap.send_dipc_message("Hello world!"))
        
        # print(rwsWrap.start_rapid_script())

        # robt = rwsWrap.get_rapid_robtarget("move_robtarget_input", "TRobRAPID")[0]

        # robt[0][0] = 800

        # print(rwsWrap.set_rapid_symbol_list(robt, "move_robtarget_input", "TRobRAPID"))

        time.sleep(2)


    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        rwsCl.logout()