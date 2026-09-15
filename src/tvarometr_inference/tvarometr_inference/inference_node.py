"""Face detection with age, gender and emotion estimation.

The camera streams continuously and this node keeps only the newest frame; the
models run when someone sends a RunInference goal. Loading them takes a while
and needs the weights on disk, so it happens on configure rather than at
startup - an unconfigured node costs nothing.

Labels come out as the models wrote them, in English. The Czech wording the
robot writes on the board is the trajectory node's business.
"""

import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, cast

import cv2
import rclpy
import torch
from cv_bridge import CvBridge
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

# MiVOLO and ResEmoteNet are vendored as-is and import themselves absolutely
# (from mivolo.model import ...), so their directory goes on the path instead of
# rewriting third-party code.
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

import numpy as np
import torch.nn.functional as F
from mivolo.model.mi_volo import MiVOLO
from mivolo.model.yolo_detector import Detector
from mivolo.structures import PersonAndFaceResult
from PIL import Image as PILImage
from resemotenet.ResEmoteNet import ResEmoteNet
from torchvision import transforms

from tvarometr_inference.annotation import draw_faces
from tvarometr_inference.attributes import (
    build_face_attributes,
    build_region_of_interest,
)
from tvarometr_inference.face_selection import Selection, select_nearest_face
from tvarometr_interfaces.action import RunInference
from tvarometr_interfaces.srv import DetectFace


class NoImage(Exception):
    """There is no camera frame to work on; the message says why."""


@dataclass
class Models:
    """All three networks, loaded together on configure."""

    detector: Detector
    mivolo: MiVOLO
    resemotenet: ResEmoteNet


@dataclass
class FrameAnalysis:
    """Every face in one frame, and which of them is the visitor."""

    boxes: list[tuple[int, int, int, int]]  # (x1, y1, x2, y2), clamped to the frame
    face_inds: list[int]  # the detector's own index for each box
    selection: Selection
    detections: PersonAndFaceResult
    # box index -> (label, confidence), full pass only
    emotions: dict[int, tuple[str, float]]
    # the selection axis this frame was judged against
    axis_x: float
    axis_falloff: float


class InferenceNode(LifecycleNode):
    def __init__(self):
        super().__init__("inference_node")

        self.NODE_NAME = "inference_node"
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()

        # Weights live outside the source tree - they are hundreds of megabytes and
        # have no business sitting next to the code. Each path can be overridden on
        # its own if you want to try a single model without moving the rest.
        self.declare_parameter("models_dir", "/opt/tvarometr/models")
        models_dir = Path(
            self.get_parameter("models_dir").get_parameter_value().string_value
        )

        self.declare_parameter(
            "detector_path", str(models_dir / "yolov8x_person_face.pt")
        )
        self.declare_parameter(
            "mivolo_path",
            str(models_dir / "model_imdb_cross_person_4.22_99.46.pth.tar"),
        )
        self.declare_parameter(
            "resemotenet_path", str(models_dir / "affectnet7_model.pth")
        )
        self.declare_parameter("device", "cpu")
        self.declare_parameter("image_topic", "/image_raw")
        # Read on every frame, so `ros2 param set` tunes them live.
        self.declare_parameter("min_face_height_px", 100)
        self.declare_parameter("ambiguity_ratio", 0.8)
        self.declare_parameter("axis_x", 0.5)
        self.declare_parameter("axis_falloff", 0.25)
        self.declare_parameter("preview_hz", 0.0)

        requested_device = (
            self.get_parameter("device").get_parameter_value().string_value
        )

        if requested_device.startswith("cuda") and not torch.cuda.is_available():
            self.logger.warning(
                f"CUDA requested ({requested_device}) but not available. Falling back to CPU."
            )
            self.device = "cpu"
        elif requested_device.startswith("cuda") and torch.cuda.is_available():
            try:
                device_id = (
                    int(requested_device.split(":")[1])
                    if ":" in requested_device
                    else 0
                )
                if device_id >= torch.cuda.device_count():
                    self.logger.warning(
                        f"CUDA device {device_id} not available. Using cuda:0 instead."
                    )
                    self.device = "cuda:0"
                else:
                    self.device = requested_device
            except (ValueError, IndexError):
                self.logger.warning(
                    f"Invalid CUDA device format: {requested_device}. Using cuda:0."
                )
                self.device = "cuda:0"
        else:
            self.device = requested_device

        self.logger.info(f"Using device: {self.device}")

        self.detector_path = (
            self.get_parameter("detector_path").get_parameter_value().string_value
        )
        self.mivolo_path = (
            self.get_parameter("mivolo_path").get_parameter_value().string_value
        )
        self.resemotenet_path = (
            self.get_parameter("resemotenet_path").get_parameter_value().string_value
        )

        self.image_topic = (
            self.get_parameter("image_topic").get_parameter_value().string_value
        )

        # The camera driver streams continuously and we only ever care about the
        # newest frame, so keep a depth of 1 and match the sensor-data QoS the
        # driver publishes with.
        image_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        self._latest_frame: Image | None = None
        self.image_subscription = self.create_subscription(
            Image, self.image_topic, self.image_callback, image_qos
        )

        self.bridge = CvBridge()
        self.debug_publisher = self.create_publisher(
            Image, f"{self.NODE_NAME}/debug_image", 1
        )

        self._models: Models | None = None
        # The preview, the action and the service all reach the same models.
        self._model_lock = threading.Lock()
        self._preview_timer = None

        self._active = False
        self.action_server = ActionServer(
            self,
            RunInference,
            f"{self.NODE_NAME}/run_inference",
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
            f"{self.NODE_NAME}/detect_face",
            self.detect_cb,
            callback_group=self.cb_group,
        )

        self.logger.info("Unconfigured - configure to load the models, then activate")

    # ============= LIFECYCLE =============

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            self._load_models()
        except Exception as e:
            self.logger.error(f"Configure failed: {e}")
            return TransitionCallbackReturn.FAILURE
        self.logger.info("Configured")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._active = True
        self.logger.info(
            f"Active - streaming from {self.image_topic}, accepting inference goals"
        )

        preview_hz = self.get_parameter("preview_hz").get_parameter_value().double_value
        if preview_hz > 0:
            self._preview_timer = self.create_timer(
                1.0 / preview_hz,
                self.preview_cb,
                callback_group=MutuallyExclusiveCallbackGroup(),
            )
            self.logger.info(
                f"Preview at {preview_hz} Hz on /{self.NODE_NAME}/debug_image"
            )
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        if self._preview_timer is not None:
            self.destroy_timer(self._preview_timer)
            self._preview_timer = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        self._models = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self._active = False
        return TransitionCallbackReturn.SUCCESS

    def _load_models(self):
        for label, path in (
            ("detector", self.detector_path),
            ("MiVOLO", self.mivolo_path),
            ("ResEmoteNet", self.resemotenet_path),
        ):
            if not Path(path).is_file():
                self.logger.error(
                    f"{label} weights not found at {path} - check the models_dir "
                    f"parameter, and that git lfs pull has been run"
                )
                raise FileNotFoundError(path)

        self.logger.info("Loading models...")
        detector = Detector(self.detector_path, self.device)
        self.logger.info("Detector loaded successfully")

        mivolo = MiVOLO(
            self.mivolo_path,
            self.device,
            half=True,
            use_persons=True,
            disable_faces=False,
        )
        self.logger.info("MiVOLO model loaded successfully")

        resemotenet = ResEmoteNet().to(self.device)
        checkpoint = torch.load(self.resemotenet_path, weights_only=False)
        resemotenet.load_state_dict(checkpoint["model_state_dict"])
        resemotenet.eval()
        self.logger.info("ResEmoteNet model loaded successfully")

        self._models = Models(detector, mivolo, resemotenet)

    def image_callback(self, msg: Image):
        self._latest_frame = msg

    # ============= ACTION =============

    def goal_cb(self, goal_request) -> GoalResponse:
        if not self._active:
            self.logger.error("Goal rejected: node is not active")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def execute_cb(self, goal_handle: ServerGoalHandle) -> RunInference.Result:
        result = RunInference.Result()
        feedback = RunInference.Feedback()

        try:
            frame, img = self._newest_image()
        except NoImage as e:
            return self._abort(goal_handle, result, str(e))

        feedback.status = "analysing"
        goal_handle.publish_feedback(feedback)
        with self._model_lock:
            analysis = self._analyse(img, full=True)
        self._publish_debug(img, analysis, frame.header)

        k = analysis.selection.index
        if k is None:
            return self._abort(goal_handle, result, self._nobody_message(analysis))
        idx = analysis.face_inds[k]
        if analysis.detections.ages[idx] is None or k not in analysis.emotions:
            return self._abort(
                goal_handle, result, "The models gave no answer for the nearest face"
            )
        if analysis.selection.ambiguous:
            self.logger.warning(
                "Two faces are nearly the same size - this may be the wrong person"
            )

        emotion, emotion_confidence = analysis.emotions[k]
        height, width = img.shape[:2]
        result.attributes = build_face_attributes(
            age=analysis.detections.ages[idx],
            gender=analysis.detections.genders[idx],
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            bbox=analysis.boxes[k],
            image_size=(width, height),
        )

        goal_handle.succeed()
        result.success = True
        result.message = (
            f"age {result.attributes.age}, {result.attributes.gender}, "
            f"{result.attributes.emotion} ({result.attributes.emotion_confidence:.3f})"
        )
        self.logger.info(result.message)
        return result

    def _abort(self, goal_handle, result, message):
        goal_handle.abort()
        result.success = False
        result.message = message
        self.logger.warning(message)
        return result

    # ============= SERVICE =============

    def detect_cb(self, request, response) -> DetectFace.Response:
        """Where the nearest face is, without the models that say anything about it.

        Quiet on the happy path: the centring loop calls this over and over.
        """
        if not self._active:
            response.success = False
            response.message = "Node is not active"
            return response

        try:
            frame, img = self._newest_image()
        except NoImage as e:
            response.success = False
            response.message = str(e)
            return response

        with self._model_lock:
            analysis = self._analyse(img, full=False)
        self._publish_debug(img, analysis, frame.header)

        k = analysis.selection.index
        if k is None:
            response.success = False
            response.message = self._nobody_message(analysis)
            return response

        height, width = img.shape[:2]
        response.face_bbox = build_region_of_interest(
            analysis.boxes[k], (width, height)
        )
        response.image_width = width
        response.image_height = height
        response.success = True

        roi = response.face_bbox
        response.message = (
            f"face at ({roi.x_offset}, {roi.y_offset}), {roi.width}x{roi.height}"
        )
        return response

    # ============= PREVIEW =============

    def preview_cb(self):
        """A full pass now and then, only to be looked at in rqt_image_view."""
        if self.debug_publisher.get_subscription_count() == 0:
            return
        try:
            frame, img = self._newest_image()
        except NoImage:
            return
        # A real request holding the models goes first; this frame is just skipped.
        if not self._model_lock.acquire(blocking=False):
            return
        try:
            analysis = self._analyse(img, full=True)
        finally:
            self._model_lock.release()
        self._publish_debug(img, analysis, frame.header)

    # ============= ANALYSIS =============

    def _newest_image(self) -> tuple[Image, np.ndarray]:
        """The newest frame and the same as a BGR array; NoImage when there is none."""
        frame = self._latest_frame
        if frame is None:
            raise NoImage(
                f"No frame received on {self.image_topic} yet - is the camera driver running?"
            )
        try:
            return frame, self.bridge.imgmsg_to_cv2(frame, desired_encoding="bgr8")
        except Exception as e:
            raise NoImage(f"Error converting image: {e}") from e

    def _analyse(self, img, full):
        """Detector over one frame; a full pass adds age, gender and emotion per face.

        The caller holds the model lock.
        """
        models = self._models
        if models is None:
            raise RuntimeError("Models are not loaded - configure the node first")

        height, width = img.shape[:2]
        detections = models.detector.predict(img)
        face_inds = detections.get_bboxes_inds("face")
        boxes = []
        for i in face_inds:
            x1, y1, x2, y2 = (
                int(v) for v in detections.get_bbox_by_ind(i, height, width)
            )
            boxes.append((x1, y1, x2, y2))
        axis_x = self.get_parameter("axis_x").get_parameter_value().double_value
        axis_falloff = (
            self.get_parameter("axis_falloff").get_parameter_value().double_value
        )
        selection = select_nearest_face(
            boxes,
            width,
            self.get_parameter("min_face_height_px")
            .get_parameter_value()
            .integer_value,
            self.get_parameter("ambiguity_ratio").get_parameter_value().double_value,
            axis_x,
            axis_falloff,
        )

        emotions = {}
        if full and face_inds:
            models.mivolo.predict(img, detections)
            for k, (x1, y1, x2, y2) in enumerate(boxes):
                if x2 > x1 and y2 > y1:
                    emotions[k] = self._predict_emotion(
                        models.resemotenet, img[y1:y2, x1:x2]
                    )

        return FrameAnalysis(
            boxes, face_inds, selection, detections, emotions, axis_x, axis_falloff
        )

    @staticmethod
    def _nobody_message(analysis):
        if not analysis.boxes:
            return "No face detected"
        return (
            f"{len(analysis.boxes)} face(s) seen, none as tall as min_face_height_px"
            " - nobody close enough"
        )

    def _publish_debug(self, img, analysis, header):
        if self.debug_publisher.get_subscription_count() == 0:
            return

        labels = []
        for k, (x1, y1, x2, y2) in enumerate(analysis.boxes):
            text = f"h{y2 - y1} w{analysis.selection.weights[k]:.2f}"
            idx = analysis.face_inds[k]
            if analysis.detections.ages[idx] is not None:
                text += f" {analysis.detections.ages[idx]:.0f} {analysis.detections.genders[idx]}"
            if k in analysis.emotions:
                emotion, confidence = analysis.emotions[k]
                text += f" {emotion} {confidence:.2f}"
            labels.append(text)

        selection = analysis.selection
        status = f"{len(analysis.boxes)} face(s)"
        if selection.index is None and analysis.boxes:
            status += " - nobody close enough"
        elif selection.ambiguous:
            status += " - AMBIGUOUS"

        annotated = draw_faces(
            img,
            analysis.boxes,
            labels,
            selection,
            status,
            analysis.axis_x,
            analysis.axis_falloff,
        )
        msg = self.bridge.cv2_to_imgmsg(annotated, encoding="bgr8")
        msg.header = header
        self.debug_publisher.publish(msg)

    # Class order of our affectnet7_model.pth, measured: 43.6% on balanced AffectNet
    # val, upstream's order 11.1%. The benchmark is in git history before b4b73bd.
    EMOTIONS: ClassVar[tuple[str, ...]] = (
        "neutral",
        "happiness",
        "sadness",
        "surprise",
        "fear",
        "disgust",
        "anger",
    )

    def _predict_emotion(self, resemotenet: ResEmoteNet, face_roi):
        """Returns (label, confidence) for the face crop."""
        transform = transforms.Compose(
            [
                transforms.Resize((64, 64)),
                transforms.Grayscale(num_output_channels=3),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )
        face_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
        pil_image = PILImage.fromarray(face_rgb)
        # ToTensor in the middle turns the image into a tensor; the stubs cannot tell.
        img_tensor = (
            cast(torch.Tensor, transform(pil_image)).unsqueeze(0).to(self.device)
        )

        with torch.no_grad():
            outputs = resemotenet(img_tensor)
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
        # Enough threads that a long goal and the preview never starve the camera.
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if executor:
            executor.shutdown(timeout_sec=5)
        if node:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
