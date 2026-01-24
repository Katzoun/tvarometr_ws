import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import sys, select, termios, tty

msg = """
Keyboard Control:
---------------------------
s - Start Inference
r - Reset
q - Quit (Emergency Stop/Quit)
e - Erase drawing (After drawing is finished)
CTRL+C to exit
"""


class KeyboardPublisher(Node):

    def __init__(self):
        super().__init__('controller')
        self.pub = self.create_publisher(String, '/pressed_key', 10)

        self.timer_period = 0.1  # 10Hz
        self.timer = self.create_timer(self.timer_period, self.timer_callback)

        self.settings = termios.tcgetattr(sys.stdin)

        print(msg)

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        select.select([sys.stdin], [], [], 0)
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        if '\x03' in key:  # Ctrl+C
            raise KeyboardInterrupt
        return key


    def timer_callback(self):
        key_str = self.get_key()
        msg = String()
        msg.data = key_str
        self.get_logger().info(f'Publishing key: {msg.data}')
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = KeyboardPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, node.settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
