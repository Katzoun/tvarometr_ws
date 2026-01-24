import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import Bool
import turtle
import threading

class TurtleDrawer(Node):
    def __init__(self):
        super().__init__('turtle_drawer')
        
        # ROS subscription for point messages
        self.point_subscriber = self.create_subscription(
            Point,
            '/point_sim',
            self.point_callback,
            10
        )
        self.clear_subscriber = self.create_subscription(Bool, '/clear_turtle', self.clear_callback, 10)

        # Drawing settings
        self.SCALE = 1
        self.X_OFFSET = -500
        self.Y_OFFSET = 0
        self.iter = 0
        
        # Initialize turtle graphics in a separate thread
        self.turtle_thread = threading.Thread(target=self.init_turtle)
        self.turtle_thread.daemon = True
        self.turtle_thread.start()
        
        self.get_logger().info('Turtle drawer node started. Listening for points on /point_sim')

    def init_turtle(self):
        """Initialize turtle graphics"""
        self.t = turtle.Turtle()
        self.wn = turtle.Screen()
        self.wn.bgcolor("white")
        self.t.color("black")
        self.t.pensize(2)
        self.t.speed(0)
        self.t.hideturtle()
        self.t.penup()
        
        # Keep turtle window open
        self.wn.mainloop()

    def point_callback(self, msg):
        """Callback for received point messages"""
        try:
            # Convert ROS coordinates to screen coordinates
            screen_x = msg.x * self.SCALE + self.X_OFFSET
            screen_y = msg.y * self.SCALE + self.Y_OFFSET
            
            # Use z coordinate to control pen (z > 0: pen up, z <= 0: pen down)
            if msg.z > 0:
                self.t.penup()
                action = "pen up"
            else:
                self.t.pendown()
                action = "pen down"
            
            # Move turtle to the point
            self.t.goto(screen_x, screen_y)
            
            self.iter += 1
            if self.iter% 50 == 0:
                self.get_logger().info(f'Drew point: ({msg.x:.2f}, {msg.y:.2f}, {msg.z:.2f}) -> screen({screen_x:.1f}, {screen_y:.1f}) [{action}]')
                self.iter = 0

        except Exception as e:
            self.get_logger().error(f'Error drawing point: {str(e)}')

    def clear_callback(self, msg):
        """Callback to clear the turtle drawing"""
        self.iter = 0
        self.t.clear()
        self.t.penup()
        self.t.goto(self.X_OFFSET, self.Y_OFFSET)
        self.get_logger().info('Turtle drawing cleared and reset to starting position')

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = TurtleDrawer()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("Node interrupted by user")
    finally:
        try:
            rclpy.shutdown()
        except Exception:
            pass

if __name__ == '__main__':
    main()
