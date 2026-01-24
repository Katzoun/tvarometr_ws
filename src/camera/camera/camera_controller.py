import rclpy
from rclpy.node import Node
import std_msgs.msg as std_msgs
import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

class WebcamPublisher(Node):
    def __init__(self):
        super().__init__('webcam_publisher')
        self.publisher_ = self.create_publisher(Image, '/input_image', 10)
        self.start_listener = self.create_subscription(std_msgs.String, '/start_inference', self.take_picture_callback, 10)
        self.bridge = CvBridge()
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            self.get_logger().error("Could not open webcam! Check if camera is connected and not used by another application.")
            raise RuntimeError("Failed to initialize webcam")
        
        # Timer pro pravidelné zobrazování kamery (50 Hz)
        self.camera_timer = self.create_timer(0.02, self.camera_callback)


    def take_picture_callback(self, msg):
        """Callback triggered when a message is received on /start_inference topic"""
        self.get_logger().info(f'Received inference request')
        
        # Capture a frame from the camera
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().error('Failed to capture image from webcam!')
            return
        
        # Convert and publish the image
        try:
            img_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            self.publisher_.publish(img_msg)
            self.get_logger().info('Image was published on /input_image')
        except Exception as e:
            self.get_logger().error(f'Error publishing image: {str(e)}')

    def camera_callback(self):
        """Timer callback for camera display"""

        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().error('Failed to read frame from camera!')
            return

        cv2.imshow('Camera', frame)
        cv2.waitKey(1)  # Required for OpenCV window to update

    def destroy_node(self):
        """Cleanup when node is destroyed"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
        self.get_logger().info('Camera resources released')
        super().destroy_node()



def main(args=None):
    rclpy.init(args=args)
    node = None
    
    try:
        node = WebcamPublisher()
        rclpy.spin(node)
    except RuntimeError as e:
        print(f"Failed to start webcam node: {e}")
    except KeyboardInterrupt:
        print("Node interrupted by user")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
