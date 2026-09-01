#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from sensor_msgs.msg import Image

import cv2
from cv_bridge import CvBridge
import torch
import json
import sys
import os

from pathlib import Path

# MiVOLO and ResEmoteNet are vendored as-is and import themselves absolutely
# (from mivolo.model import ...), so their directory goes on the path instead of
# rewriting third-party code.
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

from mivolo.model.yolo_detector import Detector
from mivolo.model.mi_volo import MiVOLO
from resemotenet.ResEmoteNet import ResEmoteNet

import torch.nn.functional as F
import torchvision.transforms as transforms
from PIL import Image as PILImage
import numpy as np

class InferenceNode(Node):
    def __init__(self):
        super().__init__('inference_node')
        
        self.get_logger().info("Initializing inference node...")

        # Weights live outside the source tree - they are hundreds of megabytes and
        # have no business sitting next to the code. Each path can be overridden on
        # its own if you want to try a single model without moving the rest.
        self.declare_parameter('models_dir', '/opt/tvarometr/models')
        models_dir = Path(self.get_parameter('models_dir').get_parameter_value().string_value)

        self.declare_parameter('detector_path', str(models_dir / 'yolov8x_person_face.pt'))
        self.declare_parameter('mivolo_path', str(models_dir / 'model_imdb_cross_person_4.22_99.46.pth.tar'))
        self.declare_parameter('resemotenet_path', str(models_dir / 'affectnet7_model.pth'))
        self.declare_parameter('device', 'cpu')  # Bezpečnější výchozí hodnota
        self.declare_parameter('image_topic', '/image_raw')
        self.declare_parameter('trigger_topic', '/start_inference')
        self.declare_parameter('output_json_topic', '/face_attributes')

        # Získání a validace device parametru
        requested_device = self.get_parameter('device').get_parameter_value().string_value
        
        # Kontrola dostupnosti CUDA
        if requested_device.startswith('cuda') and not torch.cuda.is_available():
            self.get_logger().warn(f"CUDA requested ({requested_device}) but not available. Falling back to CPU.")
            self.device = 'cpu'
        elif requested_device.startswith('cuda') and torch.cuda.is_available():
            # Ověření, že konkrétní CUDA device existuje
            try:
                device_id = int(requested_device.split(':')[1]) if ':' in requested_device else 0
                if device_id >= torch.cuda.device_count():
                    self.get_logger().warn(f"CUDA device {device_id} not available. Using cuda:0 instead.")
                    self.device = 'cuda:0'
                else:
                    self.device = requested_device
            except (ValueError, IndexError):
                self.get_logger().warn(f"Invalid CUDA device format: {requested_device}. Using cuda:0.")
                self.device = 'cuda:0'
        else:
            self.device = requested_device
            
        self.get_logger().info(f"Using device: {self.device}")

        self.detector_path = self.get_parameter('detector_path').get_parameter_value().string_value
        self.mivolo_path = self.get_parameter('mivolo_path').get_parameter_value().string_value
        self.resemotenet_path = self.get_parameter('resemotenet_path').get_parameter_value().string_value

        self.image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        self.trigger_topic = self.get_parameter('trigger_topic').get_parameter_value().string_value
        self.output_json_topic = self.get_parameter('output_json_topic').get_parameter_value().string_value

        self.publisher_ = self.create_publisher(String, self.output_json_topic, 10)

        # The camera driver streams continuously and we only ever care about the
        # newest frame, so keep a depth of 1 and match the sensor-data QoS the
        # driver publishes with.
        image_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        self._latest_frame = None
        self.image_subscription = self.create_subscription(
            Image, self.image_topic, self.image_callback, image_qos)
        self.trigger_subscription = self.create_subscription(
            String, self.trigger_topic, self.trigger_callback, 10)

        self.bridge = CvBridge()

        self._load_models()

        self.get_logger().info(
            f"Node ready, streaming from {self.image_topic}, waiting for a trigger on {self.trigger_topic}")

    def _load_models(self):
        for label, path in (('detector', self.detector_path),
                            ('MiVOLO', self.mivolo_path),
                            ('ResEmoteNet', self.resemotenet_path)):
            if not Path(path).is_file():
                self.get_logger().error(
                    f"{label} weights not found at {path} - check the models_dir "
                    f"parameter, and that git lfs pull has been run")
                raise FileNotFoundError(path)

        self.get_logger().info("Loading models...")
        self.detector = Detector(self.detector_path, self.device)
        self.get_logger().info("Detector loaded successfully")
        
        self.mivolo_model = MiVOLO(self.mivolo_path, self.device, half=True, use_persons=True, disable_faces=False)
        self.get_logger().info("MiVOLO model loaded successfully")
        
        self.resemotenet_model = ResEmoteNet().to(self.device)
        checkpoint = torch.load(self.resemotenet_path, weights_only=False)
        self.resemotenet_model.load_state_dict(checkpoint['model_state_dict'])
        self.resemotenet_model.eval()
        self.get_logger().info("ResEmoteNet model loaded successfully")

    def image_callback(self, msg):
        self._latest_frame = msg

    def trigger_callback(self, msg):
        self.get_logger().info("Inference triggered")

        frame = self._latest_frame
        if frame is None:
            self.get_logger().error(
                f"No frame received on {self.image_topic} yet - is the camera driver running?")
            return

        try:
            img = self.bridge.imgmsg_to_cv2(frame, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"Error converting image: {e}")
            return

        detections = self.detector.predict(img)
        face_inds = detections.get_bboxes_inds("face")
        if not face_inds:
            self.get_logger().info("No face detected.")
            return

        self.mivolo_model.predict(img, detections)

        idx = face_inds[0]
        x1, y1, x2, y2 = detections.get_bbox_by_ind(idx)
        age = int(round(detections.ages[idx]))
        gender = detections.genders[idx]
        gender_cz = "muz" if gender == "male" else "zena"

        face_roi = img[y1:y2, x1:x2]
        emotion, emotion_confidence = self._predict_emotion(face_roi)

        nalady = {
            "anger": "nastvany",
            "disgust": "znechuceny",
            "fear": "vydeseny",
            "happiness": "stastny",
            "sadness": "smutny",
            "surprise": "prekvapeny",
            "neutral": "neutralni",
        }

        result_json = json.dumps({
            "age": age,
            "gender": gender_cz,
            "emotion": nalady.get(emotion, "neutralni"),
            "emotion_en": emotion,
            "emotion_confidence": round(emotion_confidence, 3),
        })

        msg_out = String()
        msg_out.data = result_json
        self.publisher_.publish(msg_out)
        self.get_logger().info(f"Published: {result_json}")

    # Output order of our affectnet7_model.pth checkpoint. Measured, not assumed:
    # benchmark/ scores this order at 43.6% on a balanced AffectNet val sample and
    # confirms it is the best fitting permutation, while the order the upstream
    # ResEmoteNet inference scripts use scores 11.1% - below chance. The
    # architecture and preprocessing match upstream, but these weights clearly are
    # not theirs. Re-run benchmark/score.py before touching this.
    EMOTIONS = ['neutral', 'happiness', 'sadness', 'surprise', 'fear', 'disgust', 'anger']

    def _predict_emotion(self, face_roi):
        """Returns (label, confidence) for the face crop."""
        transform = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.Grayscale(num_output_channels=3),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        face_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(face_rgb)
        img_tensor = transform(pil_image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.resemotenet_model(img_tensor)
            probabilities = F.softmax(outputs, dim=1)

        scores = probabilities.cpu().numpy().flatten()
        max_index = int(np.argmax(scores))
        return self.EMOTIONS[max_index], float(scores[max_index])


def main(args=None):
    rclpy.init(args=args)
    node = InferenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
