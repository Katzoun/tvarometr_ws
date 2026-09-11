"""Turning what the models return into a FaceAttributes message.

Kept out of the node so it can be tested on its own: importing inference_node
pulls in torch, the vendored MiVOLO and half a gigabyte of weights, while this
is plain arithmetic over numbers the models already produced.
"""

from sensor_msgs.msg import RegionOfInterest

from tvarometr_interfaces.msg import FaceAttributes


def build_region_of_interest(bbox, image_size):
    """The detector's two corners as the one corner and a size ROS speaks.

    `bbox` is (x1, y1, x2, y2) in pixels and `image_size` the (width, height)
    of the frame it was found in. Shared with DetectFace, which answers with
    this geometry and nothing else.
    """
    width, height = (int(v) for v in image_size)
    x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)

    # A detection can hang a corner just outside the frame, and RegionOfInterest
    # counts in unsigned pixels - a negative offset would wrap into millions.
    x1 = min(max(x1, 0), width)
    y1 = min(max(y1, 0), height)
    x2 = min(max(x2, x1), width)
    y2 = min(max(y2, y1), height)

    return RegionOfInterest(
        x_offset=x1,
        y_offset=y1,
        width=x2 - x1,
        height=y2 - y1,
        do_rectify=False,
    )


def build_face_attributes(age, gender, emotion, emotion_confidence, bbox, image_size):
    """One face analysis as the message the rest of the system speaks.

    `bbox` is the detector's (x1, y1, x2, y2) in pixels and `image_size` the
    (width, height) of the frame it was found in. Labels are passed through as
    the models wrote them - the Czech wording happens in the drawing node.
    """
    width, height = (int(v) for v in image_size)

    attributes = FaceAttributes()
    attributes.age = int(round(float(age)))
    attributes.gender = gender
    attributes.emotion = emotion
    attributes.emotion_confidence = float(emotion_confidence)
    attributes.face_bbox = build_region_of_interest(bbox, image_size)
    attributes.image_width = width
    attributes.image_height = height
    return attributes
