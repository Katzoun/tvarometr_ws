"""The emotion crop: a square around the face, grown by a margin, kept in the frame."""

from tvarometr_inference.face_crop import emotion_crop

FRAME = (1920, 1080)


def test_a_tall_face_becomes_a_square_around_its_centre():
    assert emotion_crop((100, 100, 180, 200), 0.0, FRAME) == (90, 100, 190, 200)


def test_the_margin_is_added_on_each_side():
    # 100 px square, 0.3 of it on each side makes 160 px
    assert emotion_crop((500, 500, 600, 600), 0.3, FRAME) == (470, 470, 630, 630)


def test_the_frame_edge_cuts_the_crop():
    assert emotion_crop((0, 1000, 60, 1080), 0.5, FRAME) == (0, 960, 110, 1080)
