"""The centring arithmetic on its own - no robot, no camera, no ROS."""

import pytest

from tvarometr_geometry.centring import Centring

HEIGHT = 1080
# A face 220 px tall is 0.22 m, so one pixel is one millimetre.
FACE_PX = 220


def centring(**overrides):
    tuning = {
        "target_y": 0.4,
        "tolerance": 0.05,
        "gain": 0.7,
        "max_step": 0.08,
        "min_z": 0.8,
        "max_z": 1.6,
        "face_height_m": 0.22,
    }
    return Centring(**{**tuning, **overrides})


def step(z=1.2, face_centre_y=0.4 * HEIGHT, face_px=FACE_PX, **overrides):
    return centring(**overrides).step(z, face_centre_y, face_px, HEIGHT)


def test_a_face_on_target_is_centred():
    result = step(face_centre_y=0.4 * HEIGHT)
    assert result.centred
    assert result.z == 1.2
    assert result.error_px == 0


def test_a_face_just_off_target_is_still_centred():
    # 0.05 of 1080 px is the tolerance, so 50 px off does not move the camera.
    assert step(face_centre_y=0.4 * HEIGHT + 50).centred
    assert not step(face_centre_y=0.4 * HEIGHT + 60).centred


def test_a_face_low_in_the_frame_moves_the_camera_down():
    result = step(face_centre_y=0.4 * HEIGHT + 100)
    assert result.error_px == pytest.approx(100)
    # 100 px is 0.1 m of face, and the gain takes 0.7 of it.
    assert result.z == pytest.approx(1.2 - 0.07)


def test_a_face_high_in_the_frame_moves_the_camera_up():
    assert step(face_centre_y=0.4 * HEIGHT - 100).z == pytest.approx(1.2 + 0.07)


def test_a_face_further_away_asks_for_a_longer_move():
    # Half as tall on the screen means twice as far, so a pixel is 2 mm of camera.
    result = step(face_centre_y=0.4 * HEIGHT + 100, face_px=FACE_PX // 2, max_step=0.2)
    assert result.z == pytest.approx(1.2 - 0.14)


def test_a_long_move_is_cut_to_the_maximum_step():
    result = step(face_centre_y=HEIGHT, max_step=0.05)
    assert result.z == pytest.approx(1.2 - 0.05)
    assert not result.at_limit


def test_the_camera_stops_at_the_lower_limit():
    result = step(z=0.82, face_centre_y=HEIGHT)
    assert result.z == 0.8
    assert result.at_limit
    assert not result.centred


def test_the_camera_stops_at_the_upper_limit():
    result = step(z=1.58, face_centre_y=0)
    assert result.z == 1.6
    assert result.at_limit


def test_a_camera_already_at_the_limit_stays_there():
    result = step(z=0.8, face_centre_y=HEIGHT)
    assert result.z == 0.8
    assert result.at_limit


def blind(z=1.2, person_top_y=0.4 * HEIGHT, **overrides):
    return centring(**overrides).blind_step(z, person_top_y, HEIGHT)


def test_a_visitor_whose_head_sits_low_brings_the_camera_down():
    result = blind(person_top_y=0.7 * HEIGHT)
    assert result.z == pytest.approx(1.2 - 0.08)
    assert result.error_px == pytest.approx(0.3 * HEIGHT)


def test_a_visitor_whose_head_runs_off_the_top_brings_the_camera_up():
    assert blind(person_top_y=0).z == pytest.approx(1.2 + 0.08)


def test_a_head_already_where_the_face_belongs_asks_for_no_move():
    # Nothing to gain by moving: the head is in the frame, the face is turned away.
    assert blind(person_top_y=0.4 * HEIGHT) is None
    assert blind(person_top_y=0.4 * HEIGHT + 50) is None


def test_a_blind_step_stops_at_the_limit():
    result = blind(z=1.57, person_top_y=0)
    assert result.z == 1.6
    assert result.at_limit
