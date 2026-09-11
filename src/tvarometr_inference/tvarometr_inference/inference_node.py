#!/usr/bin/env python3
"""Face detection with age, gender and emotion estimation.

The camera streams continuously and this node keeps only the newest frame; the
models run when someone sends a RunInference goal. Loading them takes a while
and needs the weights on disk, so it happens on configure rather than at
startup - an unconfigured node costs nothing.

Labels come out as the models wrote them, in English. The Czech wording the
robot writes on the board is the drawing node's business.
"""

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image

import cv2
from cv_bridge import CvBridge
import torch
import sys

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

from tvarometr_interfaces.action import RunInference
from tvarometr_interfaces.srv import DetectFace
from tvarometr_inference.attributes import build_face_attributes, build_region_of_interest

class InferenceNode(LifecycleNode):
    def __init__(self):
        super().__init__('inference_node')

        self.NODE_NAME = 'inference_node'
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()

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

        # Získání a validace device parametru
        requested_device = self.get_parameter('device').get_parameter_value().string_value

        # Kontrola dostupnosti CUDA
        if requested_device.startswith('cuda') and not torch.cuda.is_available():
            self.logger.warn(f"CUDA requested ({requested_device}) but not available. Falling back to CPU.")
            self.device = 'cpu'
        elif requested_device.startswith('cuda') and torch.cuda.is_available():
            # Ověření, že konkrétní CUDA device existuje
            try:
                device_id = int(requested_device.split(':')[1]) if ':' in requested_device else 0
                if device_id >= torch.cuda.device_count():
                    self.logger.warn(f"CUDA device {device_id} not available. Using cuda:0 instead.")
                    self.device = 'cuda:0'
                else:
                    self.device = requested_device
            except (ValueError, IndexError):
                self.logger.warn(f"Invalid CUDA device format: {requested_device}. Using cuda:0.")
                self.device = 'cuda:0'
        else:
            self.device = requested_device

        self.logger.info(f"Using device: {self.device}")

        self.detector_path = self.get_parameter('detector_path').get_parameter_value().string_value
        self.mivolo_path = self.get_parameter('mivolo_path').get_parameter_value().string_value
        self.resemotenet_path = self.get_parameter('resemotenet_path').get_parameter_value().string_value

        self.image_topic = self.get_parameter('image_topic').get_parameter_value().string_value

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

        self.bridge = CvBridge()

        self.detector = None
        self.mivolo_model = None
        self.resemotenet_model = None

        self._active = False
        self.action_server = ActionServer(
            self,
            RunInference,
            f'{self.NODE_NAME}/run_inference',
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=lambda goal_handle: CancelResponse.ACCEPT,
            callback_group=self.cb_group,
        )

        # The centring loop wants the geometry many times over and none of the
        # model outputs, so the detector is reachable on its own. A service and
        # not an action: one pass over one frame, nothing to report on the way
        # and nothing worth cancelling.
        self.detect_service = self.create_service(
            DetectFace,
            f'{self.NODE_NAME}/detect_face',
            self.detect_cb,
            callback_group=self.cb_group,
        )

        self.logger.info('Unconfigured - configure to load the models, then activate')

    # ============= LIFECYCLE =============

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            self._load_models()
        except Exception as e:
            self.logger.error(f'Configure failed: {e}')
            return TransitionCallbackReturn.FAILURE
        self.logger.info('Configured')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._active = True
        self.logger.info(f'Active - streaming from {self.image_topic}, accepting inference goals')
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        self.detector = None
        self.mivolo_model = None
        self.resemotenet_model = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return TransitionCallbackReturn.SUCCESS

    def _load_models(self):
        for label, path in (('detector', self.detector_path),
                            ('MiVOLO', self.mivolo_path),
                            ('ResEmoteNet', self.resemotenet_path)):
            if not Path(path).is_file():
                self.logger.error(
                    f"{label} weights not found at {path} - check the models_dir "
                    f"parameter, and that git lfs pull has been run")
                raise FileNotFoundError(path)

        self.logger.info("Loading models...")
        self.detector = Detector(self.detector_path, self.device)
        self.logger.info("Detector loaded successfully")

        self.mivolo_model = MiVOLO(self.mivolo_path, self.device, half=True, use_persons=True, disable_faces=False)
        self.logger.info("MiVOLO model loaded successfully")

        self.resemotenet_model = ResEmoteNet().to(self.device)
        checkpoint = torch.load(self.resemotenet_path, weights_only=False)
        self.resemotenet_model.load_state_dict(checkpoint['model_state_dict'])
        self.resemotenet_model.eval()
        self.logger.info("ResEmoteNet model loaded successfully")

    def image_callback(self, msg):
        self._latest_frame = msg

    # ============= ACTION =============

    def goal_cb(self, goal_request) -> GoalResponse:
        if not self._active:
            self.logger.error('Goal rejected: node is not active')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def execute_cb(self, goal_handle: ServerGoalHandle) -> RunInference.Result:
        result = RunInference.Result()
        feedback = RunInference.Feedback()

        frame = self._latest_frame
        if frame is None:
            goal_handle.abort()
            result.success = False
            result.message = (
                f"No frame received on {self.image_topic} yet - is the camera driver running?")
            self.logger.error(result.message)
            return result

        try:
            img = self.bridge.imgmsg_to_cv2(frame, desired_encoding='bgr8')
        except Exception as e:
            goal_handle.abort()
            result.success = False
            result.message = f'Error converting image: {e}'
            self.logger.error(result.message)
            return result

        feedback.status = 'detecting'
        goal_handle.publish_feedback(feedback)

        detections = self.detector.predict(img)
        face_inds = detections.get_bboxes_inds("face")
        if not face_inds:
            goal_handle.abort()
            result.success = False
            result.message = 'No face detected'
            self.logger.info(result.message)
            return result

        feedback.status = 'estimating age and gender'
        goal_handle.publish_feedback(feedback)
        self.mivolo_model.predict(img, detections)

        idx = face_inds[0]
        bbox = detections.get_bbox_by_ind(idx)
        x1, y1, x2, y2 = (int(v) for v in bbox)

        feedback.status = 'classifying emotion'
        goal_handle.publish_feedback(feedback)
        emotion, emotion_confidence = self._predict_emotion(img[y1:y2, x1:x2])

        height, width = img.shape[:2]
        result.attributes = build_face_attributes(
            age=detections.ages[idx],
            gender=detections.genders[idx],
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            bbox=bbox,
            image_size=(width, height),
        )

        goal_handle.succeed()
        result.success = True
        result.message = (
            f'age {result.attributes.age}, {result.attributes.gender}, '
            f'{result.attributes.emotion} ({result.attributes.emotion_confidence:.3f})')
        self.logger.info(result.message)
        return result

    # ============= SERVICE =============

    def detect_cb(self, request, response) -> DetectFace.Response:
        """Where the face is, without the models that say anything about it.

        Deliberately quiet on the happy path: a centring loop calls this many
        times a second and a log line per call would bury everything else.

        Assumes callers do not overlap with a RunInference goal - the tree
        sequences them - because both reach the same detector object.
        """
        if not self._active:
            response.success = False
            response.message = 'Node is not active'
            return response

        frame = self._latest_frame
        if frame is None:
            response.success = False
            response.message = (
                f'No frame received on {self.image_topic} yet - '
                'is the camera driver running?')
            return response

        try:
            img = self.bridge.imgmsg_to_cv2(frame, desired_encoding='bgr8')
        except Exception as e:
            response.success = False
            response.message = f'Error converting image: {e}'
            self.logger.error(response.message)
            return response

        detections = self.detector.predict(img)
        face_inds = detections.get_bboxes_inds("face")
        if not face_inds:
            response.success = False
            response.message = 'No face detected'
            return response

        height, width = img.shape[:2]
        response.face_bbox = build_region_of_interest(
            detections.get_bbox_by_ind(face_inds[0]), (width, height))
        response.image_width = width
        response.image_height = height
        response.success = True

        roi = response.face_bbox
        response.message = (
            f'face at ({roi.x_offset}, {roi.y_offset}), {roi.width}x{roi.height}')
        return response

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
    node = None
    executor = None
    try:
        node = InferenceNode()
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if executor:
            executor.shutdown(timeout_sec=5)
        if node:
            node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
