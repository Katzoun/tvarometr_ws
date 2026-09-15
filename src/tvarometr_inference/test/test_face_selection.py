"""Picking the visitor out of a crowd by face height and distance from the axis."""

import pytest

from tvarometr_inference.face_selection import axis_weight, select_nearest_face

WIDTH = 1000


def box(height, centre_x=500, width=None):
    """A face box of the given height; width defaults to a face-like 0.8 of it."""
    width = width or int(0.8 * height)
    x1 = centre_x - width // 2
    return (x1, 100, x1 + width, 100 + height)


def select(boxes, min_height_px=100, ambiguity_ratio=0.8, axis_x=0.5, axis_falloff=0.0):
    return select_nearest_face(
        boxes, WIDTH, min_height_px, ambiguity_ratio, axis_x, axis_falloff
    )


def test_no_faces_selects_nobody():
    result = select([])
    assert result.index is None
    assert result.too_small == ()


def test_the_tallest_face_wins():
    assert select([box(150), box(300), box(200)]).index == 1


def test_height_decides_not_width():
    # A head turned to the side: narrow but tall, and still the nearest person.
    assert select([box(300, width=120), box(250, width=240)]).index == 0


def test_faces_below_the_minimum_are_rejected():
    result = select([box(80), box(150)])
    assert result.index == 1
    assert result.too_small == (0,)


def test_only_distant_faces_means_nobody_is_there():
    result = select([box(60), box(90)])
    assert result.index is None
    assert result.too_small == (0, 1)


def test_a_clear_winner_is_not_ambiguous():
    assert not select([box(300), box(150)]).ambiguous


def test_a_runner_up_almost_as_tall_is_ambiguous():
    result = select([box(300), box(260)])
    assert result.index == 0
    assert result.ambiguous


def test_a_rejected_face_does_not_make_it_ambiguous():
    assert not select([box(110), box(95)], min_height_px=100).ambiguous


def test_weight_is_one_on_the_axis_and_halves_at_the_falloff():
    assert axis_weight(box(200, centre_x=500), WIDTH, 0.5, 0.25) == pytest.approx(1.0)
    assert axis_weight(box(200, centre_x=750), WIDTH, 0.5, 0.25) == pytest.approx(0.5)
    assert axis_weight(box(200, centre_x=0), WIDTH, 0.5, 0.25) == pytest.approx(0.0625)


def test_a_falloff_of_zero_ignores_position():
    assert axis_weight(box(200, centre_x=0), WIDTH, 0.5, 0.0) == 1.0
    assert select([box(250, centre_x=500), box(300, centre_x=50)]).index == 1


def test_a_face_on_the_axis_beats_a_slightly_taller_one_far_from_it():
    faces = [box(300, centre_x=950), box(260, centre_x=500)]
    assert select(faces, axis_falloff=0.25).index == 1


def test_a_much_nearer_face_still_wins_off_the_axis():
    faces = [box(400, centre_x=650), box(150, centre_x=500)]
    assert select(faces, axis_falloff=0.25).index == 0


def test_moving_the_axis_moves_the_preference():
    faces = [box(250, centre_x=200), box(250, centre_x=800)]
    assert select(faces, axis_x=0.2, axis_falloff=0.2).index == 0
    assert select(faces, axis_x=0.8, axis_falloff=0.2).index == 1


def test_the_minimum_height_ignores_the_axis():
    result = select([box(90, centre_x=500)], axis_falloff=0.25)
    assert result.index is None
    assert result.too_small == (0,)


def test_equal_heights_far_apart_on_the_axis_are_not_ambiguous():
    faces = [box(250, centre_x=500), box(250, centre_x=950)]
    assert not select(faces, axis_falloff=0.2).ambiguous
