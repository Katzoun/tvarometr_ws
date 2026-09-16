"""Turning what the models return into a FaceAttributes message.

Kept apart from the node so it tests without torch or the weights.
"""

from sensor_msgs.msg import RegionOfInterest

from tvarometr_interfaces.msg import FaceAttributes


def build_region_of_interest(bbox, image_size):
    """(x1, y1, x2, y2) pixels as a RegionOfInterest, clamped to the frame.

    `image_size` is (width, height); DetectFace answers with this too.
    """
    width, height = (int(v) for v in image_size)
    x1, y1, x2, y2 = (round(float(v)) for v in bbox)

    # A detection can hang a corner just outside the frame, and RegionOfInterest
    # counts in unsigned pixels - a negative offset would wrap into millions.
    x1 = min(max(x1, 0), width)
    y1 = min(max(y1, 0), height)
    x2 = min(max(x2, x1), width)
    y2 = min(max(y2, y1), height)

    return RegionOfInterest(
        x_offset=x1, y_offset=y1, width=x2 - x1, height=y2 - y1, do_rectify=False
    )


def build_face_attributes(age, gender, emotion, emotion_confidence, bbox, image_size):
    """One face analysis as FaceAttributes; labels stay the models' English."""
    width, height = (int(v) for v in image_size)

    attributes = FaceAttributes()
    attributes.age = round(float(age))
    attributes.gender = gender
    attributes.emotion = emotion
    attributes.emotion_confidence = float(emotion_confidence)
    attributes.face_bbox = build_region_of_interest(bbox, image_size)
    attributes.image_width = width
    attributes.image_height = height
    return attributes
