"""Picking the visitor out of a crowd: the nearest face, or the widest body."""

import pytest

from tvarometr_inference.visitor_selection import axis_weight, select_visitor

WIDTH = 1000


def person(width, centre_x=500, top=100, bottom=900):
    x1 = centre_x - width // 2
    return (x1, top, x1 + width, bottom)


def face(height, centre_x=500, top=150):
    return (centre_x - height // 2, top, centre_x + height // 2, top + height)


def select(
    persons,
    faces=None,
    face_of_person=None,
    min_face_height_px=100,
    min_width_px=200,
    **overrides,
):
    settings = {"ambiguity_ratio": 0.8, "axis_x": 0.5, "axis_falloff": 0.0}
    return select_visitor(
        persons,
        faces or [],
        face_of_person or {},
        WIDTH,
        min_face_height_px,
        min_width_px,
        **{**settings, **overrides},
    )


def test_no_people_means_no_visitor():
    result = select([])
    assert result.person is None
    assert result.face is None


def test_the_widest_person_wins():
    assert select([person(250), person(400), person(300)]).person == 1


def test_width_decides_not_height():
    # Somebody close, cut off by the top of the frame: short box, still nearest.
    cut_off = person(500, top=0, bottom=400)
    assert select([cut_off, person(300)]).person == 0


def test_people_below_the_minimum_width_are_rejected():
    result = select([person(150), person(300)])
    assert result.person == 1
    assert result.too_far == (0,)


def test_only_distant_people_means_nobody_is_there():
    result = select([person(100), person(180)])
    assert result.person is None
    assert result.too_far == (0, 1)


def test_a_clear_winner_is_not_ambiguous():
    assert not select([person(500), person(250)]).ambiguous


def test_a_runner_up_almost_as_wide_is_ambiguous():
    result = select([person(500), person(450)])
    assert result.person == 0
    assert result.ambiguous


def test_a_rejected_person_does_not_make_it_ambiguous():
    assert not select([person(210), person(190)]).ambiguous


def test_the_visitors_face_comes_with_them():
    # Both faces are too small to decide, so width picks the visitor and the face
    # comes along.
    result = select(
        [person(300), person(500)],
        faces=[face(40), face(50)],
        face_of_person={0: 0, 1: 1},
    )
    assert result.person == 1
    assert result.face == 1


def test_a_visitor_whose_face_is_out_of_frame_is_still_the_visitor():
    # Only the bystander has a face; the visitor's head is above the frame.
    result = select(
        [person(500, top=0), person(250)], faces=[face(40)], face_of_person={1: 0}
    )
    assert result.person == 0
    assert result.face is None


def test_the_tallest_face_wins_over_a_wider_body():
    # A child at the mark against an adult further back: the child's head is bigger
    # on screen, their body is not.
    child, adult = person(450, centre_x=400), person(520, centre_x=600)
    result = select(
        [child, adult],
        faces=[face(300, centre_x=400), face(150, centre_x=600)],
        face_of_person={0: 0, 1: 1},
    )
    assert result.person == 0
    assert result.by_face
    assert result.too_far == ()


def test_a_face_too_small_to_count_leaves_its_person_too_far():
    result = select(
        [person(450), person(520, centre_x=700)],
        faces=[face(300), face(80, centre_x=700)],
        face_of_person={0: 0, 1: 1},
    )
    assert result.person == 0
    assert result.too_far == (1,)


def test_bodies_decide_while_no_face_is_tall_enough():
    result = select(
        [person(300), person(500)], faces=[face(50)], face_of_person={0: 0}
    )
    assert result.person == 1
    assert not result.by_face


def test_a_small_face_close_up_still_beats_a_distant_body():
    # Nobody's face counts, so the fallback runs and the child at the mark wins.
    result = select(
        [person(430), person(250, centre_x=800)],
        faces=[face(90)],
        face_of_person={0: 0},
        min_width_px=400,
    )
    assert result.person == 0
    assert result.too_far == (1,)


def test_nobody_counts_when_every_face_and_body_is_small():
    result = select(
        [person(150), person(180, centre_x=700)],
        faces=[face(60)],
        face_of_person={0: 0},
    )
    assert result.person is None
    assert result.face is None
    assert result.too_far == (0, 1)


def test_weight_is_one_on_the_axis_and_halves_at_the_falloff():
    assert axis_weight(person(200, centre_x=500), WIDTH, 0.5, 0.25) == pytest.approx(
        1.0
    )
    assert axis_weight(person(200, centre_x=750), WIDTH, 0.5, 0.25) == pytest.approx(
        0.5
    )
    assert axis_weight(person(200, centre_x=0), WIDTH, 0.5, 0.25) == pytest.approx(
        0.0625
    )


def test_a_falloff_of_zero_ignores_position():
    assert axis_weight(person(200, centre_x=0), WIDTH, 0.5, 0.0) == 1.0
    assert select([person(300, centre_x=500), person(400, centre_x=50)]).person == 1


def test_somebody_on_the_axis_beats_a_slightly_wider_one_far_from_it():
    people = [person(400, centre_x=950), person(350, centre_x=500)]
    assert select(people, axis_falloff=0.25).person == 1


def test_a_much_nearer_person_still_wins_off_the_axis():
    people = [person(600, centre_x=650), person(250, centre_x=500)]
    assert select(people, axis_falloff=0.25).person == 0


def test_moving_the_axis_moves_the_preference():
    people = [person(300, centre_x=200), person(300, centre_x=800)]
    assert select(people, axis_x=0.2, axis_falloff=0.2).person == 0
    assert select(people, axis_x=0.8, axis_falloff=0.2).person == 1


def test_the_minimum_width_ignores_the_axis():
    result = select([person(150, centre_x=500)], axis_falloff=0.25)
    assert result.person is None
    assert result.too_far == (0,)
