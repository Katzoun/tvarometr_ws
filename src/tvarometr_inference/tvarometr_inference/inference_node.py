"""Face detection with age, gender and emotion estimation.

One thread runs the models on the newest frame; requests only read its results.
"""

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, cast

import cv2
import rclpy
import torch
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import Node as LifecycleNode
from rclpy.lifecycle import State, TransitionCallbackReturn
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import CompressedImage

# MiVOLO and ResEmoteNet are vendored as-is and import themselves absolutely.
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

import numpy as np
import torch.nn.functional as F
from mivolo.model.mi_volo import MiVOLO
from mivolo.model.yolo_detector import Detector
from mivolo.structures import PersonAndFaceResult
from PIL import Image as PILImage
from resemotenet.ResEmoteNet import ResEmoteNet
from torchvision import transforms

from tvarometr_inference.annotation import draw_debug, draw_scene
from tvarometr_inference.attribute_averaging import Sample, average, male_probability
from tvarometr_inference.attributes import (
    build_face_attributes,
    build_region_of_interest,
)
from tvarometr_inference.face_crop import emotion_crop
from tvarometr_inference.visitor_selection import Visitor, select_visitor
from tvarometr_interfaces.action import RunInference
from tvarometr_interfaces.srv import DetectFace


class NoImage(Exception):
    """There is no analysed frame to answer from; the message says why."""


@dataclass
class Models:
    """All three networks, loaded together on configure."""

    detector: Detector
    mivolo: MiVOLO
    resemotenet: ResEmoteNet


@dataclass
class FrameAnalysis:
    """Everyone in one frame, which of them is the visitor, and their face."""

    persons: list[tuple[int, int, int, int]]  # (x1, y1, x2, y2), clamped to the frame
    faces: list[tuple[int, int, int, int]]
    person_inds: list[int]  # the detector's own index for each person box
    face_inds: list[int]  # and for each face box
    visitor: Visitor
    detections: PersonAndFaceResult
    # The visitor's emotion, one probability per label; full pass only.
    emotion_probabilities: tuple[float, ...] | None
    # the selection axis this frame was judged against
    axis_x: float
    axis_falloff: float


@dataclass
class AnalysedFrame:
    """The loop's latest result, as the requests read it."""

    stamp: Time  # when the camera took the frame
    width: int
    height: int
    analysis: FrameAnalysis


class InferenceNode(LifecycleNode):
    def __init__(self):
        super().__init__("inference_node")

        self.NODE_NAME = "inference_node"
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()

        # Weights live outside the source tree; each path can be overridden alone.
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
            "resemotenet_path", str(models_dir / "ResEmoteNetBS64.pth")
        )
        self.declare_parameter("device", "cpu")
        self.declare_parameter("image_topic", "/image_raw/compressed")
        # Read on every frame, so `ros2 param set` tunes them live.
        self.declare_parameter("min_person_width_px", 300)
        self.declare_parameter("ambiguity_ratio", 0.8)
        self.declare_parameter("axis_x", 0.5)
        self.declare_parameter("axis_falloff", 0.25)
        self.declare_parameter("emotion_margin", 0.3)
        # How long DetectFace waits for a frame taken after not_before.
        self.declare_parameter("fresh_frame_timeout_s", 2.0)
        # RunInference averages the visitor's face over this many frames, and
        # gives up when fewer than min_samples arrive within the timeout.
        self.declare_parameter("samples", 10)
        self.declare_parameter("min_samples", 5)
        self.declare_parameter("sample_timeout_s", 5.0)
        self.declare_parameter("jpeg_quality", 80)

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

        # Only the newest frame matters, and it stays JPEG until the loop takes it.
        image_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        self._frame: CompressedImage | None = None
        self._frame_arrived = threading.Condition()
        self.image_subscription = self.create_subscription(
            CompressedImage, self.image_topic, self.image_callback, image_qos
        )

        # JPEG too: a raw 1080p frame is 6 MB, too much to push out at loop rate.
        self.debug_publisher = self.create_publisher(
            CompressedImage, f"{self.NODE_NAME}/debug_image/compressed", 1
        )
        # The same selection without labels, for the TV beside the robot.
        self.scene_publisher = self.create_publisher(
            CompressedImage, f"{self.NODE_NAME}/scene_image/compressed", 1
        )

        self._models: Models | None = None

        # What the loop hands over. The condition's lock guards both: the latest
        # result, and the list a RunInference goal is collecting samples into.
        self._analysed = threading.Condition()
        self._latest: AnalysedFrame | None = None
        self._samples: list[Sample] | None = None

        self._stop = threading.Event()
        self._loop: threading.Thread | None = None

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

        # Only reads the loop's latest result: nothing to report, nothing to cancel.
        self.detect_service = self.create_service(
            DetectFace,
            f"{self.NODE_NAME}/detect_face",
            self.detect_cb,
            callback_group=self.cb_group,
        )

        self.logger.info("Unconfigured - configure to load the models, then activate")

    def _int(self, name: str) -> int:
        return self.get_parameter(name).get_parameter_value().integer_value

    def _double(self, name: str) -> float:
        return self.get_parameter(name).get_parameter_value().double_value

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
        self._stop.clear()
        self._loop = threading.Thread(target=self._perception_loop, daemon=True)
        self._loop.start()
        self._active = True
        self.logger.info(
            f"Active - analysing {self.image_topic}, accepting inference goals"
        )
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._stop_loop()
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._stop_loop()
        self._models = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self._stop_loop()
        return TransitionCallbackReturn.SUCCESS

    def destroy_node(self):
        # The loop publishes; it has to be gone before the node's publishers are.
        self._stop_loop()
        super().destroy_node()

    def _stop_loop(self):
        self._active = False
        self._stop.set()
        with self._frame_arrived:
            self._frame_arrived.notify_all()
        if self._loop is not None:
            self._loop.join()
            self._loop = None
        with self._analysed:
            self._latest = None

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
        # BS64 is a bare state dict, affectnet7_model.pth wraps it.
        resemotenet.load_state_dict(checkpoint.get("model_state_dict", checkpoint))
        resemotenet.eval()
        self.logger.info("ResEmoteNet model loaded successfully")

        self._models = Models(detector, mivolo, resemotenet)

    def image_callback(self, msg: CompressedImage):
        with self._frame_arrived:
            self._frame = msg
            self._frame_arrived.notify()

    # ============= LOOP =============

    def _perception_loop(self):
        """The only code that runs the models: newest frame in, result out."""
        try:
            self._analyse_frames()
        except Exception:
            # Ctrl+C shuts ROS down under a running loop; only complain otherwise.
            if self.context.ok():
                raise

    def _analyse_frames(self):
        done = None
        while not self._stop.is_set():
            with self._frame_arrived:
                self._frame_arrived.wait_for(
                    lambda last=done: self._stop.is_set() or self._frame is not last,
                    timeout=0.5,
                )
                frame = self._frame
            if self._stop.is_set() or frame is None or frame is done:
                continue
            done = frame

            img = cv2.imdecode(np.frombuffer(frame.data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                self.logger.warning(
                    f"Could not decode a frame from {self.image_topic}",
                    throttle_duration_sec=5.0,
                )
                continue

            collecting = self._samples is not None
            watching_debug = self.debug_publisher.get_subscription_count() > 0
            try:
                analysis = self._analyse(img, full=collecting or watching_debug)
            except Exception as e:
                # One bad frame, or a GPU hiccup: the next frame gets its chance.
                self.logger.error(f"Analysis failed: {e}", throttle_duration_sec=5.0)
                continue

            self._publish_images(img, analysis, frame.header)

            sample = self._sample(analysis) if collecting else None
            height, width = img.shape[:2]
            with self._analysed:
                self._latest = AnalysedFrame(
                    Time.from_msg(frame.header.stamp), width, height, analysis
                )
                if sample is not None and self._samples is not None:
                    self._samples.append(sample)
                self._analysed.notify_all()

    def _sample(self, analysis) -> Sample | None:
        """The models' answer for the visitor's face, if this frame has one."""
        visitor = analysis.visitor
        if visitor.face is None or analysis.emotion_probabilities is None:
            return None
        idx = analysis.face_inds[visitor.face]
        age = analysis.detections.ages[idx]
        gender = analysis.detections.genders[idx]
        score = analysis.detections.gender_scores[idx]
        if age is None or gender is None or score is None:
            return None
        return Sample(
            age=age,
            male_probability=male_probability(gender, score),
            emotion_probabilities=analysis.emotion_probabilities,
            face_bbox=analysis.faces[visitor.face],
        )

    # ============= ACTION =============

    def goal_cb(self, goal_request) -> GoalResponse:
        if not self._active:
            self.logger.error("Goal rejected: node is not active")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def execute_cb(self, goal_handle: ServerGoalHandle) -> RunInference.Result:
        """Collects the visitor's face from several frames and averages them."""
        result = RunInference.Result()
        feedback = RunInference.Feedback()
        wanted = self._int("samples")
        needed = max(1, min(self._int("min_samples"), wanted))
        timeout = self._double("sample_timeout_s")

        samples: list[Sample] = []
        with self._analysed:
            if self._samples is not None:
                return self._abort(
                    goal_handle, result, "Already analysing - one goal at a time"
                )
            self._samples = samples

        deadline = time.monotonic() + timeout
        reported = None
        latest = None
        try:
            while True:
                with self._analysed:
                    self._analysed.wait(timeout=0.1)
                    count = len(samples)
                if count != reported:
                    feedback.status = f"collecting {count}/{wanted}"
                    goal_handle.publish_feedback(feedback)
                    reported = count
                if (
                    count >= wanted
                    or goal_handle.is_cancel_requested
                    or time.monotonic() >= deadline
                ):
                    break
        finally:
            with self._analysed:
                self._samples = None
                latest = self._latest

        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            result.success = False
            result.message = "Cancelled"
            return result

        if len(samples) < needed:
            reason = ""
            if latest is not None:
                if latest.analysis.visitor.person is None:
                    reason = f" - {self._nobody_message(latest.analysis)}"
                elif latest.analysis.visitor.face is None:
                    reason = " - the visitor's face is not in view"
            return self._abort(
                goal_handle,
                result,
                f"Only {len(samples)} of {needed} frames with the visitor's face "
                f"within {timeout:.1f} s{reason}",
            )
        if latest is not None and latest.analysis.visitor.ambiguous:
            self.logger.warning(
                "Two people are nearly the same width - this may be the wrong person"
            )

        averaged = average(samples, self.EMOTIONS)
        image_size = (latest.width, latest.height) if latest is not None else (0, 0)
        result.attributes = build_face_attributes(
            age=averaged.age,
            gender=averaged.gender,
            emotion=averaged.emotion,
            emotion_confidence=averaged.emotion_confidence,
            bbox=averaged.face_bbox,
            image_size=image_size,
        )

        goal_handle.succeed()
        result.success = True
        result.message = (
            f"age {result.attributes.age}, {result.attributes.gender}, "
            f"{result.attributes.emotion} ({result.attributes.emotion_confidence:.3f})"
            f" from {len(samples)} frames"
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
        """Where the visitor is, from the loop's latest result.

        Quiet on the happy path: the centring loop calls this over and over.
        """
        if not self._active:
            response.success = False
            response.message = "Node is not active"
            return response

        try:
            frame = self._analysed_after(request.not_before)
        except NoImage as e:
            response.success = False
            response.message = str(e)
            return response

        analysis = frame.analysis
        visitor = analysis.visitor
        if visitor.person is None:
            response.success = False
            response.message = self._nobody_message(analysis)
            return response

        size = (frame.width, frame.height)
        person = analysis.persons[visitor.person]
        response.person_bbox = build_region_of_interest(person, size)
        response.image_width = frame.width
        response.image_height = frame.height
        response.success = True

        if visitor.face is None:
            response.message = (
                f"visitor {person[2] - person[0]} px wide, their face is not in view"
            )
            return response

        response.face_bbox = build_region_of_interest(
            analysis.faces[visitor.face], size
        )
        roi = response.face_bbox
        response.message = (
            f"face at ({roi.x_offset}, {roi.y_offset}), {roi.width}x{roi.height}"
        )
        return response

    def _analysed_after(self, not_before) -> AnalysedFrame:
        """The loop's latest result, waiting for a frame taken at or after `not_before`.

        A zero `not_before` takes whatever was analysed last.
        """
        timeout = self._double("fresh_frame_timeout_s")
        wanted = (
            Time.from_msg(not_before)
            if (not_before.sec or not_before.nanosec)
            else None
        )

        def fresh_enough():
            latest = self._latest
            return latest is not None and (wanted is None or latest.stamp >= wanted)

        with self._analysed:
            ready = self._analysed.wait_for(fresh_enough, timeout=timeout)
            latest = self._latest
        if latest is None:
            raise NoImage(
                f"No frame analysed from {self.image_topic} - is the camera running?"
            )
        if not ready:
            raise NoImage(
                f"No frame taken after not_before analysed within {timeout:.1f} s"
            )
        return latest

    # ============= ANALYSIS =============

    def _analyse(self, img, full):
        """Detector over one frame; a full pass adds age, gender and emotion.

        Called from the loop only; emotion for the visitor's face alone.
        """
        models = self._models
        if models is None:
            raise RuntimeError("Models are not loaded - configure the node first")

        height, width = img.shape[:2]
        detections = models.detector.predict(img)
        # Which face belongs to whom. MiVOLO does this for itself on a full pass;
        # the visitor has to be picked on every pass, full or not.
        detections.associate_faces_with_persons()
        person_inds = detections.get_bboxes_inds("person")
        face_inds = detections.get_bboxes_inds("face")
        persons = self._boxes(detections, person_inds, height, width)
        faces = self._boxes(detections, face_inds, height, width)

        face_of_person = {}
        for k, face_ind in enumerate(face_inds):
            person_ind = detections.face_to_person_map.get(face_ind)
            if person_ind in person_inds:
                face_of_person[person_inds.index(person_ind)] = k

        axis_x = self.get_parameter("axis_x").get_parameter_value().double_value
        axis_falloff = (
            self.get_parameter("axis_falloff").get_parameter_value().double_value
        )
        visitor = select_visitor(
            persons,
            face_of_person,
            width,
            self.get_parameter("min_person_width_px")
            .get_parameter_value()
            .integer_value,
            self.get_parameter("ambiguity_ratio").get_parameter_value().double_value,
            axis_x,
            axis_falloff,
        )

        emotion_probabilities = None
        if full and visitor.face is not None:
            models.mivolo.predict(img, detections)
            x1, y1, x2, y2 = emotion_crop(
                faces[visitor.face], self._double("emotion_margin"), (width, height)
            )
            if x2 > x1 and y2 > y1:
                emotion_probabilities = self._predict_emotion(
                    models.resemotenet, img[y1:y2, x1:x2]
                )

        return FrameAnalysis(
            persons,
            faces,
            person_inds,
            face_inds,
            visitor,
            detections,
            emotion_probabilities,
            axis_x,
            axis_falloff,
        )

    @staticmethod
    def _boxes(detections, inds, height, width) -> list[tuple[int, int, int, int]]:
        """The detector's boxes as (x1, y1, x2, y2), clamped to the frame."""
        boxes = []
        for i in inds:
            x1, y1, x2, y2 = (
                int(v) for v in detections.get_bbox_by_ind(i, height, width)
            )
            boxes.append((x1, y1, x2, y2))
        return boxes

    @staticmethod
    def _nobody_message(analysis):
        if not analysis.persons:
            return "Nobody detected"
        return (
            f"{len(analysis.persons)} person(s) seen, none as wide as"
            " min_person_width_px - nobody close enough"
        )

    def _publish_images(self, img, analysis, header):
        """Both views of one analysis, each only if someone is watching."""
        if self.scene_publisher.get_subscription_count() > 0:
            scene = draw_scene(img, analysis.persons, analysis.faces, analysis.visitor)
            self._publish_jpeg(self.scene_publisher, scene, header)
        if self.debug_publisher.get_subscription_count() == 0:
            return

        visitor = analysis.visitor
        labels = []
        for k, (x1, y1, x2, y2) in enumerate(analysis.persons):
            text = f"w{x2 - x1} x{visitor.weights[k]:.2f}"
            face = visitor.face if k == visitor.person else None
            if face is not None:
                idx = analysis.face_inds[face]
                if analysis.detections.ages[idx] is not None:
                    text += (
                        f" {analysis.detections.ages[idx]:.0f}"
                        f" {analysis.detections.genders[idx]}"
                    )
                probabilities = analysis.emotion_probabilities
                if probabilities is not None:
                    top = np.argsort(probabilities)[::-1][:3]
                    text += " " + ", ".join(
                        f"{self.EMOTIONS[k]} {probabilities[k]:.2f}" for k in top
                    )
            labels.append(text)

        status = f"{len(analysis.persons)} person(s)"
        if visitor.person is None:
            if analysis.persons:
                status += " - nobody close enough"
        else:
            if visitor.face is None:
                status += " - visitor's face not in view"
            if visitor.ambiguous:
                status += " - AMBIGUOUS"
        if self._samples is not None:
            status += " - COLLECTING"

        annotated = draw_debug(
            img,
            analysis.persons,
            analysis.faces,
            labels,
            visitor,
            status,
            analysis.axis_x,
            analysis.axis_falloff,
        )
        self._publish_jpeg(self.debug_publisher, annotated, header)

    def _publish_jpeg(self, publisher, image, header):
        ok, jpeg = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self._int("jpeg_quality")]
        )
        if not ok:
            return
        msg = CompressedImage()
        msg.header = header
        msg.format = "jpeg"
        msg.data.frombytes(jpeg.tobytes())
        publisher.publish(msg)

    # Class order of ResEmoteNetBS64.pth, the best fit in benchmark/ (60.1% on balanced
    # AffectNet val). affectnet7_model.pth has another; measure any new checkpoint.
    EMOTIONS: ClassVar[tuple[str, ...]] = (
        "happiness",
        "surprise",
        "sadness",
        "anger",
        "disgust",
        "fear",
        "neutral",
    )

    def _predict_emotion(self, resemotenet: ResEmoteNet, face_roi) -> tuple[float, ...]:
        """One probability per label in EMOTIONS for the face crop."""
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

        return tuple(float(p) for p in probabilities.cpu().numpy().flatten())


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = InferenceNode()
        # Goals and DetectFace calls wait on the loop, each on a thread of its own,
        # and the camera callback must still get one.
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
