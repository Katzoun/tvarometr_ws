"""The bounding box changes shape on the way into the message.

A detector reports two corners, RegionOfInterest holds one corner and a size,
and it counts in unsigned pixels - so a corner that falls outside the frame has
to be brought back in before it wraps into millions.
"""

from tvarometr_inference.attributes import build_face_attributes


def attributes(bbox=(10, 20, 110, 220), image_size=(640, 480), **kwargs):
    """A message with everything but the field under test left at a sane value."""
    defaults = dict(age=30, gender="male", emotion="neutral", emotion_confidence=0.5)
    defaults.update(kwargs)
    return build_face_attributes(bbox=bbox, image_size=image_size, **defaults)


def test_two_corners_become_a_corner_and_a_size():
    roi = attributes(bbox=(10, 20, 110, 220)).face_bbox
    assert (roi.x_offset, roi.y_offset) == (10, 20)
    assert (roi.width, roi.height) == (100, 200)


def test_a_corner_left_of_the_frame_is_pulled_back_to_zero():
    roi = attributes(bbox=(-15, -5, 100, 100)).face_bbox
    assert (roi.x_offset, roi.y_offset) == (0, 0)
    assert (roi.width, roi.height) == (100, 100)


def test_a_corner_past_the_edge_stops_at_the_frame():
    roi = attributes(bbox=(600, 400, 700, 500), image_size=(640, 480)).face_bbox
    assert (roi.x_offset, roi.y_offset) == (600, 400)
    assert (roi.width, roi.height) == (40, 80)


def test_a_box_entirely_outside_the_frame_collapses_instead_of_wrapping():
    roi = attributes(bbox=(-200, -200, -100, -100)).face_bbox
    assert (roi.width, roi.height) == (0, 0)


def test_float_corners_round_to_whole_pixels():
    roi = attributes(bbox=(10.4, 20.6, 110.4, 220.6)).face_bbox
    assert (roi.x_offset, roi.y_offset) == (10, 21)
    assert (roi.width, roi.height) == (100, 200)


def test_the_frame_size_is_recorded_alongside_the_box():
    result = attributes(image_size=(1280, 720))
    assert (result.image_width, result.image_height) == (1280, 720)


def test_age_arrives_as_a_whole_year():
    assert attributes(age=31.6).age == 32


def test_labels_stay_in_the_models_own_english():
    result = attributes(gender="female", emotion="happiness", emotion_confidence=0.82)
    assert result.gender == "female"
    assert result.emotion == "happiness"
    assert round(result.emotion_confidence, 3) == 0.82
